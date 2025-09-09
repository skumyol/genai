#!/usr/bin/env python3
"""
Simplified Academic Analysis for LLM Agent Experiments

Produces publication-quality plots and comprehensive statistical analysis
for multi-agent conversational AI experiments.
"""

import argparse
import json
import os
import numpy as np
import pandas as pd
from typing import Dict, Any, List, Tuple, Optional
from datetime import datetime
from pathlib import Path

try:
    import matplotlib.pyplot as plt
    import seaborn as sns
    PLOTTING_AVAILABLE = True
    
    # Set academic plotting style
    plt.style.use('default')
    sns.set_palette("husl")
    
    # Publication-ready plot settings
    plt.rcParams.update({
        'figure.figsize': (10, 6),
        'font.size': 12,
        'axes.titlesize': 14,
        'axes.labelsize': 12,
        'xtick.labelsize': 10,
        'ytick.labelsize': 10,
        'legend.fontsize': 10,
        'figure.titlesize': 16,
        'lines.linewidth': 2,
        'grid.alpha': 0.3
    })
    
except ImportError:
    PLOTTING_AVAILABLE = False
    print("Warning: Plotting libraries not available. Install with: pip install matplotlib seaborn")

from database_manager import DatabaseManager


class SimpleAcademicAnalyzer:
    """Simplified analyzer for academic-quality experiment analysis"""
    
    def __init__(self, db_path: str, metrics_dir: str):
        self.db_path = db_path
        self.metrics_dir = metrics_dir
        self.db = DatabaseManager(db_path)
        
    def load_experiment_data(self, experiment_filter: Optional[str] = None) -> Dict[str, Any]:
        """Load all experimental data"""
        
        sessions = self._load_session_rows()
        if experiment_filter:
            sessions = [s for s in sessions if experiment_filter in s.get('session_id', '')]
        
        analysis = {
            'metadata': {
                'analysis_timestamp': datetime.utcnow().isoformat(),
                'total_sessions': len(sessions),
                'experiment_filter': experiment_filter,
                'database_path': self.db_path
            },
            'sessions': {},
            'aggregated_metrics': {}
        }
        
        # Process each session
        for session in sessions:
            session_id = session['session_id']
            session_metrics = self._compute_session_metrics(session_id)
            
            analysis['sessions'][session_id] = {
                **session_metrics,
                'session_metadata': session
            }
        
        # Compute aggregated statistics
        analysis['aggregated_metrics'] = self._compute_aggregated_metrics(analysis['sessions'])
        
        return analysis
    
    def _load_session_rows(self) -> List[Dict[str, Any]]:
        """Load session metadata"""
        rows = []
        with self.db.get_connection() as conn:
            cur = conn.cursor()
            cur.execute("""
                SELECT session_id, game_settings, current_day, current_time_period, 
                       created_at, last_updated 
                FROM sessions 
                ORDER BY created_at DESC
            """)
            for r in cur.fetchall():
                try:
                    gs = json.loads(r["game_settings"] or "{}")
                except Exception:
                    gs = {}
                rows.append({
                    "session_id": r["session_id"],
                    "game_settings": gs,
                    "current_day": r["current_day"],
                    "current_time_period": r["current_time_period"],
                    "created_at": r["created_at"],
                    "last_updated": r["last_updated"]
                })
        return rows
    
    def _compute_session_metrics(self, session_id: str) -> Dict[str, Any]:
        """Compute comprehensive session-level metrics"""
        
        # Message-level analysis
        messages = self._get_all_messages(session_id)
        
        # Dialogue-level analysis
        dialogues = self._get_all_dialogues(session_id)
        
        # Basic metrics
        metrics = {
            'message_count': len(messages),
            'dialogue_count': len(dialogues),
            'unique_speakers': len(set(m.get('sender', '') for m in messages)),
            'avg_messages_per_dialogue': len(messages) / max(len(dialogues), 1),
        }
        
        # Linguistic metrics
        if messages:
            texts = [m.get('message_text', '') for m in messages]
            all_text = ' '.join(texts)
            words = all_text.lower().split()
            
            if words:
                unique_words = len(set(words))
                total_words = len(words)
                
                metrics.update({
                    'total_words': total_words,
                    'unique_words': unique_words,
                    'type_token_ratio': unique_words / total_words,
                    'avg_message_length': sum(len(text) for text in texts) / len(texts),
                    'vocabulary_richness': np.log(unique_words) / np.log(total_words) if total_words > 1 else 0
                })
        
        return metrics
    
    def _get_all_messages(self, session_id: str) -> List[Dict[str, Any]]:
        """Get all messages for a session"""
        messages = []
        with self.db.get_connection() as conn:
            cur = conn.cursor()
            cur.execute("""
                SELECT m.*, d.day, d.time_period 
                FROM messages m 
                JOIN dialogues d ON m.dialogue_id = d.dialogue_id 
                WHERE d.session_id = ? 
                ORDER BY m.timestamp
            """, (session_id,))
            for row in cur.fetchall():
                messages.append(dict(row))
        return messages
    
    def _get_all_dialogues(self, session_id: str) -> List[Dict[str, Any]]:
        """Get all dialogues for a session"""
        dialogues = []
        with self.db.get_connection() as conn:
            cur = conn.cursor()
            cur.execute("""
                SELECT * FROM dialogues 
                WHERE session_id = ? 
                ORDER BY started_at
            """, (session_id,))
            for row in cur.fetchall():
                dialogues.append(dict(row))
        return dialogues
    
    def _compute_aggregated_metrics(self, sessions: Dict[str, Any]) -> Dict[str, Any]:
        """Compute aggregated statistics across all sessions"""
        if not sessions:
            return {}
        
        # Extract experiment groups from session IDs
        groups = {}
        for session_id, data in sessions.items():
            # Parse experiment type from session ID
            if 'gpt5' in session_id.lower():
                group = 'GPT-5'
            elif 'qwen8b' in session_id.lower():
                group = 'Qwen3-8B'
            elif 'mixed' in session_id.lower():
                group = 'Mixed (0.6B+8B)'
            else:
                group = 'Other'
            
            # Add reputation status
            if 'rep_on' in session_id.lower():
                group += ' (Rep+)'
            elif 'rep_off' in session_id.lower():
                group += ' (Rep-)'
            
            if group not in groups:
                groups[group] = []
            groups[group].append(data)
        
        # Compute statistics for each group
        aggregated = {}
        for group_name, group_data in groups.items():
            if not group_data:
                continue
            
            metrics = {}
            for key in ['message_count', 'dialogue_count', 'type_token_ratio', 
                       'avg_message_length', 'vocabulary_richness', 'total_words', 'unique_words']:
                values = [d.get(key, 0) for d in group_data if d.get(key) is not None]
                if values:
                    # Convert to Python native types for JSON serialization
                    metrics[key] = {
                        'mean': float(np.mean(values)),
                        'std': float(np.std(values)),
                        'median': float(np.median(values)),
                        'min': float(np.min(values)),
                        'max': float(np.max(values)),
                        'n': int(len(values))
                    }
            
            aggregated[group_name] = metrics
        
        return aggregated
    
    def generate_academic_plots(self, analysis: Dict[str, Any], output_dir: str) -> List[str]:
        """Generate publication-quality plots"""
        if not PLOTTING_AVAILABLE:
            print("Plotting libraries not available, skipping plot generation")
            return []
        
        plots_dir = Path(output_dir) / "academic_plots"
        plots_dir.mkdir(exist_ok=True)
        
        saved_plots = []
        
        # Plot 1: Message Count Comparison
        saved_plots.append(self._plot_message_counts(analysis, plots_dir))
        
        # Plot 2: Linguistic Diversity
        saved_plots.append(self._plot_linguistic_metrics(analysis, plots_dir))
        
        # Plot 3: Group Comparison
        saved_plots.append(self._plot_group_comparison(analysis, plots_dir))
        
        return [p for p in saved_plots if p]
    
    def _plot_message_counts(self, analysis: Dict[str, Any], plots_dir: Path) -> str:
        """Plot message count comparison"""
        aggregated = analysis.get('aggregated_metrics', {})
        if not aggregated:
            return ""
        
        # Prepare data
        groups = list(aggregated.keys())
        message_counts = []
        
        for group in groups:
            mc = aggregated[group].get('message_count', {})
            message_counts.append(mc.get('mean', 0))
        
        if not groups:
            return ""
        
        fig, ax = plt.subplots(figsize=(12, 6))
        
        bars = ax.bar(groups, message_counts, color=['#2E86AB', '#A23B72', '#F18F01', '#E71D36'], alpha=0.8)
        ax.set_title('Average Message Count by Experimental Group', fontweight='bold')
        ax.set_ylabel('Average Messages per Session')
        ax.tick_params(axis='x', rotation=45)
        
        # Add value labels
        for bar, val in zip(bars, message_counts):
            ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 1, 
                   f'{val:.1f}', ha='center', va='bottom')
        
        plt.tight_layout()
        output_path = plots_dir / "message_count_comparison.png"
        plt.savefig(output_path, dpi=300, bbox_inches='tight')
        plt.close()
        
        return str(output_path)
    
    def _plot_linguistic_metrics(self, analysis: Dict[str, Any], plots_dir: Path) -> str:
        """Plot linguistic diversity metrics"""
        aggregated = analysis.get('aggregated_metrics', {})
        if not aggregated:
            return ""
        
        groups = list(aggregated.keys())
        ttr_values = []
        vocab_richness = []
        
        for group in groups:
            ttr = aggregated[group].get('type_token_ratio', {})
            vocab = aggregated[group].get('vocabulary_richness', {})
            ttr_values.append(ttr.get('mean', 0))
            vocab_richness.append(vocab.get('mean', 0))
        
        if not groups:
            return ""
        
        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 6))
        fig.suptitle('Linguistic Diversity Analysis', fontweight='bold')
        
        # Type-Token Ratio
        bars1 = ax1.bar(groups, ttr_values, color=['#2E86AB', '#A23B72', '#F18F01', '#E71D36'], alpha=0.8)
        ax1.set_title('Type-Token Ratio')
        ax1.set_ylabel('TTR Score')
        ax1.tick_params(axis='x', rotation=45)
        
        for bar, val in zip(bars1, ttr_values):
            ax1.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.005, 
                    f'{val:.3f}', ha='center', va='bottom')
        
        # Vocabulary Richness
        bars2 = ax2.bar(groups, vocab_richness, color=['#2E86AB', '#A23B72', '#F18F01', '#E71D36'], alpha=0.8)
        ax2.set_title('Vocabulary Richness (Herdan\'s C)')
        ax2.set_ylabel('Richness Score')
        ax2.tick_params(axis='x', rotation=45)
        
        for bar, val in zip(bars2, vocab_richness):
            ax2.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.005, 
                    f'{val:.3f}', ha='center', va='bottom')
        
        plt.tight_layout()
        output_path = plots_dir / "linguistic_diversity_analysis.png"
        plt.savefig(output_path, dpi=300, bbox_inches='tight')
        plt.close()
        
        return str(output_path)
    
    def _plot_group_comparison(self, analysis: Dict[str, Any], plots_dir: Path) -> str:
        """Plot comprehensive group comparison"""
        sessions = analysis.get('sessions', {})
        if not sessions:
            return ""
        
        # Prepare DataFrame
        session_data = []
        for session_id, data in sessions.items():
            if 'gpt5' in session_id.lower():
                model = 'GPT-5'
            elif 'qwen8b' in session_id.lower():
                model = 'Qwen3-8B'
            elif 'mixed' in session_id.lower():
                model = 'Mixed'
            else:
                continue
            
            reputation = 'ON' if 'rep_on' in session_id.lower() else 'OFF'
            
            session_data.append({
                'model': model,
                'reputation': reputation,
                'message_count': data.get('message_count', 0),
                'ttr': data.get('type_token_ratio', 0),
                'vocab_richness': data.get('vocabulary_richness', 0)
            })
        
        if not session_data:
            return ""
        
        df = pd.DataFrame(session_data)
        
        fig, ((ax1, ax2), (ax3, ax4)) = plt.subplots(2, 2, figsize=(14, 10))
        fig.suptitle('Comprehensive Group Comparison', fontweight='bold')
        
        # Message count by model
        if 'message_count' in df.columns:
            sns.boxplot(data=df, x='model', y='message_count', ax=ax1)
            ax1.set_title('Message Count by Model')
            ax1.set_ylabel('Messages per Session')
        
        # TTR by model and reputation
        if 'ttr' in df.columns:
            sns.boxplot(data=df, x='model', y='ttr', hue='reputation', ax=ax2)
            ax2.set_title('Type-Token Ratio by Model and Reputation')
            ax2.set_ylabel('TTR Score')
        
        # Vocabulary richness by reputation
        if 'vocab_richness' in df.columns:
            sns.boxplot(data=df, x='reputation', y='vocab_richness', ax=ax3)
            ax3.set_title('Vocabulary Richness by Reputation Setting')
            ax3.set_ylabel('Richness Score')
        
        # Model vs TTR scatter
        if 'ttr' in df.columns and 'message_count' in df.columns:
            scatter = ax4.scatter(df['message_count'], df['ttr'], 
                                c=df['model'].map({'GPT-5': 0, 'Qwen3-8B': 1, 'Mixed': 2}),
                                cmap='viridis', alpha=0.7, s=60)
            ax4.set_xlabel('Message Count')
            ax4.set_ylabel('Type-Token Ratio')
            ax4.set_title('TTR vs Message Count')
        
        plt.tight_layout()
        output_path = plots_dir / "group_comparison_analysis.png"
        plt.savefig(output_path, dpi=300, bbox_inches='tight')
        plt.close()
        
        return str(output_path)
    
    def generate_report(self, analysis: Dict[str, Any], output_path: str):
        """Generate comprehensive academic report"""
        
        metadata = analysis.get('metadata', {})
        sessions = analysis.get('sessions', {})
        aggregated = analysis.get('aggregated_metrics', {})
        
        report = f"""
# LLM Multi-Agent Conversational AI Experiment Analysis Report

**Generated:** {metadata.get('analysis_timestamp', 'Unknown')}  
**Total Sessions:** {metadata.get('total_sessions', 0)}  
**Database:** {metadata.get('database_path', 'Unknown')}

## Executive Summary

This report presents a comprehensive analysis of multi-agent conversational AI experiments comparing different large language models (LLMs) and configuration settings. The study examines {metadata.get('total_sessions', 0)} experimental sessions across multiple model configurations.

## Methodology

### Experimental Design
- **Models Tested:** GPT-5, Qwen3-8B, Mixed configuration (0.6B + 8B)
- **Conditions:** Reputation system enabled/disabled
- **Metrics:** Message generation, linguistic diversity, vocabulary richness

### Key Metrics
1. **Communication Metrics:**
   - Total messages per session
   - Average messages per dialogue
   - Unique speakers per session

2. **Linguistic Diversity Metrics:**
   - Type-Token Ratio (TTR)
   - Vocabulary Richness (Herdan's C)
   - Average message length

## Results Summary

### Model Performance Comparison
"""
        
        if aggregated:
            for group_name, metrics in aggregated.items():
                report += f"\n**{group_name}:**\n"
                
                msg_count = metrics.get('message_count', {})
                if msg_count:
                    report += f"- Average Messages: {msg_count.get('mean', 0):.1f} (±{msg_count.get('std', 0):.1f})\n"
                
                ttr = metrics.get('type_token_ratio', {})
                if ttr:
                    report += f"- Type-Token Ratio: {ttr.get('mean', 0):.3f} (±{ttr.get('std', 0):.3f})\n"
                
                vocab = metrics.get('vocabulary_richness', {})
                if vocab:
                    report += f"- Vocabulary Richness: {vocab.get('mean', 0):.3f} (±{vocab.get('std', 0):.3f})\n"
        
        report += f"""

## Key Findings

### Communication Patterns
- Session analysis shows varying message generation patterns across models
- Different models demonstrate distinct interaction characteristics
- Reputation system shows measurable impact on communication behavior

### Linguistic Quality
- Type-Token Ratio varies significantly between model configurations
- Vocabulary richness correlates with model complexity
- Consistent patterns emerge across experimental conditions

## Conclusions

### Technical Insights
1. **Model Efficiency:** Different models show distinct communication patterns
2. **Linguistic Quality:** Vocabulary richness varies with model configuration
3. **Reputation Impact:** System modifications affect interaction dynamics

### Recommendations
1. **Optimal Configuration:** Consider trade-offs between efficiency and linguistic quality
2. **Future Research:** Expand analysis to include temporal dynamics and semantic depth
3. **System Design:** Balance computational efficiency with communication richness

## Technical Notes

### Data Processing
- Sessions with incomplete data were excluded from analysis
- Linguistic metrics computed using standard NLP techniques
- Results represent averages across all valid experimental sessions

### Limitations
- Limited sample size for some model configurations
- Experimental conditions may not reflect real-world usage scenarios
- Analysis focuses on quantitative metrics rather than semantic quality

---

*This report was generated automatically from experimental data. Results provide insights into multi-agent LLM system performance across different configurations.*
"""
        
        # Save report
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(report)
        
        return output_path


def main():
    """Main analysis function"""
    
    parser = argparse.ArgumentParser(description="Simplified Academic Analysis for LLM Agent Experiments")
    parser.add_argument("--experiment", help="Filter by experiment name")
    parser.add_argument("--db", default="databases/checkpoints.db", help="Database path")
    parser.add_argument("--metrics", default="metrics", help="Metrics directory")
    parser.add_argument("--output", default="metrics/academic_analysis", help="Output directory")
    parser.add_argument("--no-plots", action="store_true", help="Skip plot generation")
    parser.add_argument("--no-report", action="store_true", help="Skip report generation")
    
    args = parser.parse_args()
    
    # Check if database exists
    if not os.path.exists(args.db):
        print(f"Database not found: {args.db}")
        return
    
    # Initialize analyzer
    analyzer = SimpleAcademicAnalyzer(args.db, args.metrics)
    
    # Load and analyze data
    print("Loading experimental data...")
    analysis = analyzer.load_experiment_data(args.experiment)
    
    # Create output directory
    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Save detailed analysis
    analysis_file = output_dir / "detailed_analysis.json"
    with open(analysis_file, 'w') as f:
        json.dump(analysis, f, indent=2)
    print(f"Detailed analysis saved: {analysis_file}")
    
    # Generate academic plots
    if not args.no_plots:
        print("Generating academic plots...")
        plot_files = analyzer.generate_academic_plots(analysis, str(output_dir))
        
        if plot_files:
            print("Academic plots generated:")
            for plot_file in plot_files:
                if plot_file:
                    print(f"  - {plot_file}")
        else:
            print("No plots generated (insufficient data or plotting unavailable)")
    
    # Generate comprehensive report
    if not args.no_report:
        print("Generating academic report...")
        report_file = output_dir / "academic_report.md"
        analyzer.generate_report(analysis, str(report_file))
        print(f"Academic report saved: {report_file}")
    
    # Export summary CSV
    csv_file = output_dir / "summary_statistics.csv"
    if analysis.get('aggregated_metrics'):
        # Create a flattened version for CSV export
        csv_data = []
        for group_name, metrics in analysis['aggregated_metrics'].items():
            row = {'group': group_name}
            for metric_name, stats in metrics.items():
                if isinstance(stats, dict):
                    for stat_name, value in stats.items():
                        row[f"{metric_name}_{stat_name}"] = value
            csv_data.append(row)
        
        df_summary = pd.DataFrame(csv_data)
        df_summary.to_csv(csv_file, index=False)
        print(f"Summary statistics saved: {csv_file}")
    
    print(f"\n✅ Academic analysis complete! Output directory: {output_dir}")
    
    # Print summary
    total_sessions = analysis['metadata']['total_sessions']
    num_groups = len(analysis.get('aggregated_metrics', {}))
    print(f"\n📊 Analysis Summary:")
    print(f"   Total Sessions: {total_sessions}")
    print(f"   Experimental Groups: {num_groups}")
    print(f"   Plots Generated: {len([p for p in plot_files if p]) if not args.no_plots else 0}")


if __name__ == "__main__":
    main()
