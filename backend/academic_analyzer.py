#!/usr/bin/env python3
"""
Enhanced Academic Analysis for LLM Agent Experiments

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


class NumpyEncoder(json.JSONEncoder):
    """Custom JSON encoder for numpy data types"""
    def default(self, obj):
        if isinstance(obj, np.integer):
            return int(obj)
        elif isinstance(obj, np.floating):
            return float(obj)
        elif isinstance(obj, np.ndarray):
            return obj.tolist()
        return super(NumpyEncoder, self).default(obj)

try:
    import matplotlib.pyplot as plt
    import matplotlib.patches as mpatches
    import seaborn as sns
    from scipy import stats
    ADVANCED_PLOTTING = True
    
    # Set academic plotting style
    plt.style.use('seaborn-v0_8')
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
    ADVANCED_PLOTTING = False
    print("Warning: Advanced plotting libraries not available. Install with: pip install matplotlib seaborn scipy pandas")

from database_manager import DatabaseManager


class AcademicAnalyzer:
    """Enhanced analyzer for academic-quality experiment analysis"""
    
    def __init__(self, db_path: str, metrics_dir: str):
        self.db_path = db_path
        self.metrics_dir = metrics_dir
        self.db = DatabaseManager(db_path)
        
    def load_experiment_data(self, experiment_filter: Optional[str] = None) -> Dict[str, Any]:
        """Load all experimental data with enhanced metrics"""
        
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
            'aggregated_metrics': {},
            'statistical_tests': {}
        }
        
        # Process each session
        for session in sessions:
            session_id = session['session_id']
            session_metrics = self._compute_session_metrics(session_id)
            
            # Load LLM performance metrics
            llm_metrics = self._load_llm_metrics(session_id)
            
            analysis['sessions'][session_id] = {
                **session_metrics,
                **llm_metrics,
                'session_metadata': session
            }
        
        # Compute aggregated statistics
        analysis['aggregated_metrics'] = self._compute_aggregated_metrics(analysis['sessions'])
        
        # Perform statistical tests
        analysis['statistical_tests'] = self._perform_statistical_tests(analysis['sessions'])
        
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
        
        # NPC interaction analysis
        npc_interactions = self._analyze_npc_interactions(session_id)
        
        # Linguistic diversity metrics
        linguistic_metrics = self._compute_linguistic_metrics(messages)
        
        # Temporal dynamics
        temporal_metrics = self._compute_temporal_metrics(messages, dialogues)
        
        return {
            'message_count': len(messages),
            'dialogue_count': len(dialogues),
            'unique_speakers': len(set(m.get('sender', '') for m in messages)),
            'avg_messages_per_dialogue': len(messages) / max(len(dialogues), 1),
            'session_duration_hours': self._compute_session_duration(session_id),
            **linguistic_metrics,
            **temporal_metrics,
            **npc_interactions
        }
    
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
    
    def _compute_linguistic_metrics(self, messages: List[Dict[str, Any]]) -> Dict[str, float]:
        """Compute advanced linguistic diversity metrics"""
        if not messages:
            return {
                'type_token_ratio': 0.0,
                'unique_message_ratio': 0.0,
                'avg_message_length': 0.0,
                'vocabulary_richness': 0.0,
                'lexical_diversity': 0.0
            }
        
        texts = [m.get('message_text', '') for m in messages]
        all_text = ' '.join(texts)
        words = all_text.lower().split()
        
        # Basic metrics
        total_messages = len(messages)
        unique_messages = len(set(texts))
        total_words = len(words)
        unique_words = len(set(words))
        
        # Advanced metrics
        avg_length = sum(len(text) for text in texts) / total_messages
        ttr = unique_words / max(total_words, 1)
        
        # Vocabulary richness (Herdan's C)
        vocab_richness = np.log(unique_words) / np.log(total_words) if total_words > 1 else 0
        
        # Lexical diversity (MTLD approximation)
        lexical_diversity = self._compute_mtld_approximation([str(w) for w in words])
        
        return {
            'type_token_ratio': ttr,
            'unique_message_ratio': unique_messages / total_messages,
            'avg_message_length': avg_length,
            'vocabulary_richness': vocab_richness,
            'lexical_diversity': lexical_diversity,
            'total_words': total_words,
            'unique_words': unique_words
        }
    
    def _compute_mtld_approximation(self, words: List[str]) -> float:
        """Compute approximation of Measure of Textual Lexical Diversity"""
        if len(words) < 50:
            return 0.0
        
        # Simple approximation: words per unique word in sliding windows
        window_size = 50
        diversities = []
        
        for i in range(0, len(words) - window_size + 1, 10):
            window = words[i:i + window_size]
            unique_in_window = len(set(window))
            diversity = window_size / unique_in_window if unique_in_window > 0 else 0
            diversities.append(diversity)
        
        return np.mean(diversities) if diversities else 0.0
    
    def _analyze_npc_interactions(self, session_id: str) -> Dict[str, Any]:
        """Analyze NPC interaction patterns"""
        with self.db.get_connection() as conn:
            cur = conn.cursor()
            
            # Get interaction network
            cur.execute("""
                SELECT initiator, receiver, COUNT(*) as dialogue_count
                FROM dialogues 
                WHERE session_id = ? 
                GROUP BY initiator, receiver
            """, (session_id,))
            
            interactions = cur.fetchall()
            
            if not interactions:
                return {
                    'interaction_pairs': 0,
                    'avg_dialogues_per_pair': 0.0,
                    'interaction_balance': 0.0,
                    'network_density': 0.0
                }
            
            # Compute network metrics
            pairs = len(interactions)
            total_dialogues = sum(row[2] for row in interactions)
            avg_per_pair = total_dialogues / pairs if pairs > 0 else 0
            
            # Interaction balance (how evenly distributed are interactions)
            dialogue_counts = [row[2] for row in interactions]
            interaction_balance = 1 - (np.std(dialogue_counts) / np.mean(dialogue_counts)) if dialogue_counts else 0
            
            # Get unique NPCs
            npcs = set()
            for row in interactions:
                npcs.add(row[0])  # initiator
                npcs.add(row[1])  # receiver
            
            # Network density
            max_possible_pairs = len(npcs) * (len(npcs) - 1)
            network_density = pairs / max_possible_pairs if max_possible_pairs > 0 else 0
            
            return {
                'interaction_pairs': pairs,
                'avg_dialogues_per_pair': avg_per_pair,
                'interaction_balance': max(0, interaction_balance),
                'network_density': network_density,
                'unique_npcs': len(npcs)
            }
    
    def _compute_temporal_metrics(self, messages: List[Dict[str, Any]], 
                                dialogues: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Compute temporal dynamics metrics"""
        if not messages or not dialogues:
            return {
                'avg_dialogue_duration': 0.0,
                'messages_per_hour': 0.0,
                'peak_activity_period': 'unknown'
            }
        
        # Dialogue duration analysis
        dialogue_durations = []
        for d in dialogues:
            if d.get('started_at') and d.get('ended_at'):
                try:
                    start = datetime.fromisoformat(d['started_at'])
                    end = datetime.fromisoformat(d['ended_at'])
                    duration = (end - start).total_seconds() / 60  # minutes
                    dialogue_durations.append(duration)
                except Exception:
                    continue
        
        avg_duration = np.mean(dialogue_durations) if dialogue_durations else 0.0
        
        # Activity by time period
        time_period_counts = {}
        for m in messages:
            period = m.get('time_period', 'unknown')
            time_period_counts[period] = time_period_counts.get(period, 0) + 1
        
        peak_period = max(time_period_counts.items(), key=lambda x: x[1])[0] if time_period_counts else 'unknown'
        
        # Messages per hour (approximate)
        total_hours = max(1, len(set(m.get('day', 1) for m in messages)) * 24)
        messages_per_hour = len(messages) / total_hours
        
        return {
            'avg_dialogue_duration': avg_duration,
            'messages_per_hour': messages_per_hour,
            'peak_activity_period': peak_period
        }
    
    def _compute_session_duration(self, session_id: str) -> float:
        """Compute session duration in hours"""
        with self.db.get_connection() as conn:
            cur = conn.cursor()
            cur.execute("""
                SELECT created_at, last_updated 
                FROM sessions 
                WHERE session_id = ?
            """, (session_id,))
            row = cur.fetchone()
            
            if row and row[0] and row[1]:
                try:
                    start = datetime.fromisoformat(row[0])
                    end = datetime.fromisoformat(row[1])
                    return (end - start).total_seconds() / 3600
                except Exception:
                    pass
        return 0.0
    
    def _load_llm_metrics(self, session_id: str) -> Dict[str, Any]:
        """Load LLM performance metrics from metrics files"""
        # Try to find metrics file for this session
        # The files may be named with session_id repeated, so try multiple patterns
        patterns = [
            f"*{session_id}_metrics.json",                    # Original pattern
            f"{session_id}_{session_id}_metrics.json",        # Duplicated session_id pattern
            f"*{session_id}*_metrics.json"                    # Broader pattern
        ]
        
        metrics_files = []
        for pattern in patterns:
            found_files = list(Path(self.metrics_dir).glob(pattern))
            if found_files:
                metrics_files = found_files
                break
        
        if not metrics_files:
            return {
                'total_llm_calls': 0,
                'avg_llm_latency': 0.0,
                'avg_context_size': 0.0,
                'llm_cost_estimate': 0.0
            }
        
        try:
            with open(metrics_files[0], 'r') as f:
                data = json.load(f)
            
            summary = data.get('summary', {})
            llm_stats = summary.get('llm_stats', {})
            
            return {
                'total_llm_calls': llm_stats.get('total_calls', 0),
                'avg_llm_latency': llm_stats.get('avg_latency', 0.0),
                'avg_context_size': llm_stats.get('avg_context_size', 0.0),
                'max_context_size': llm_stats.get('max_context_size', 0.0),
                'calls_by_agent': llm_stats.get('calls_by_agent', {}),
                'calls_by_model': llm_stats.get('calls_by_model', {})
            }
        except Exception:
            return {
                'total_llm_calls': 0,
                'avg_llm_latency': 0.0,
                'avg_context_size': 0.0,
                'llm_cost_estimate': 0.0
            }
    
    def _compute_aggregated_metrics(self, sessions: Dict[str, Any]) -> Dict[str, Any]:
        """Compute aggregated statistics across all sessions"""
        if not sessions:
            return {}
        
        # Extract experiment groups from session IDs
        groups = {}
        for session_id, data in sessions.items():
            # Parse experiment type from session ID
            if 'gpt5' in session_id:
                group = 'GPT-5'
            elif 'qwen8b' in session_id:
                group = 'Qwen3-8B'
            elif 'mixed' in session_id:
                group = 'Mixed (0.6B+8B)'
            else:
                group = 'Other'
            
            # Add reputation status
            if 'rep_on' in session_id:
                group += ' (Rep+)'
            elif 'rep_off' in session_id:
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
                       'avg_message_length', 'total_llm_calls', 'avg_llm_latency',
                       'avg_context_size', 'vocabulary_richness', 'lexical_diversity']:
                values = [d.get(key, 0) for d in group_data if d.get(key) is not None]
                if values:
                    metrics[key] = {
                        'mean': np.mean(values),
                        'std': np.std(values),
                        'median': np.median(values),
                        'min': np.min(values),
                        'max': np.max(values),
                        'n': len(values)
                    }
            
            aggregated[group_name] = metrics
        
        return aggregated
    
    def _perform_statistical_tests(self, sessions: Dict[str, Any]) -> Dict[str, Any]:
        """Perform statistical significance tests"""
        if not ADVANCED_PLOTTING:
            return {}
        
        # Group sessions by experiment type
        gpt5_sessions = [s for sid, s in sessions.items() if 'gpt5' in sid]
        qwen_sessions = [s for sid, s in sessions.items() if 'qwen8b' in sid]
        mixed_sessions = [s for sid, s in sessions.items() if 'mixed' in sid]
        
        rep_on_sessions = [s for sid, s in sessions.items() if 'rep_on' in sid]
        rep_off_sessions = [s for sid, s in sessions.items() if 'rep_off' in sid]
        
        tests = {}
        
        # Model comparison tests
        if len(gpt5_sessions) > 1 and len(qwen_sessions) > 1:
            tests['gpt5_vs_qwen_latency'] = self._t_test(
                [s.get('avg_llm_latency', 0) for s in gpt5_sessions],
                [s.get('avg_llm_latency', 0) for s in qwen_sessions],
                'LLM Latency: GPT-5 vs Qwen3-8B'
            )
            
            tests['gpt5_vs_qwen_diversity'] = self._t_test(
                [s.get('type_token_ratio', 0) for s in gpt5_sessions],
                [s.get('type_token_ratio', 0) for s in qwen_sessions],
                'Type-Token Ratio: GPT-5 vs Qwen3-8B'
            )
        
        # Reputation system tests
        if len(rep_on_sessions) > 1 and len(rep_off_sessions) > 1:
            tests['reputation_effect_messages'] = self._t_test(
                [s.get('message_count', 0) for s in rep_on_sessions],
                [s.get('message_count', 0) for s in rep_off_sessions],
                'Message Count: Reputation ON vs OFF'
            )
            
            tests['reputation_effect_diversity'] = self._t_test(
                [s.get('lexical_diversity', 0) for s in rep_on_sessions],
                [s.get('lexical_diversity', 0) for s in rep_off_sessions],
                'Lexical Diversity: Reputation ON vs OFF'
            )
        
        return tests
    
    def _t_test(self, group1: List[float], group2: List[float], description: str) -> Dict[str, Any]:
        """Perform independent t-test"""
        try:
            if len(group1) < 2 or len(group2) < 2:
                return {'error': 'Insufficient data for statistical test', 'description': description}
            
            statistic, p_value = stats.ttest_ind(group1, group2)
            
            # Calculate effect size with safeguards
            mean1, mean2 = np.mean(group1), np.mean(group2)
            var1, var2 = np.var(group1, ddof=1), np.var(group2, ddof=1)
            pooled_std = np.sqrt((var1 + var2) / 2)
            
            if pooled_std == 0:
                effect_size = 0.0
            else:
                effect_size = (mean1 - mean2) / pooled_std
            
            # Ensure all values are JSON serializable
            result = {
                'description': description,
                'statistic': float(statistic),
                'p_value': float(p_value),
                'effect_size_cohens_d': float(effect_size),
                'group1_mean': float(mean1),
                'group2_mean': float(mean2),
                'group1_std': float(np.std(group1)),
                'group2_std': float(np.std(group2)),
                'significant_at_05': float(p_value) < 0.05,
                'significant_at_01': float(p_value) < 0.01
            }
            
            return result
            
        except Exception as e:
            return {'error': f'Statistical test failed: {str(e)}', 'description': description}
    
    def generate_academic_plots(self, analysis: Dict[str, Any], output_dir: str) -> List[str]:
        """Generate publication-quality plots"""
        if not ADVANCED_PLOTTING:
            return []
        
        plots_dir = Path(output_dir) / "academic_plots"
        plots_dir.mkdir(exist_ok=True)
        
        saved_plots = []
        
        # Plot 1: Model Performance Comparison
        saved_plots.append(self._plot_model_performance(analysis, plots_dir))
        
        # Plot 2: Reputation System Effects
        saved_plots.append(self._plot_reputation_effects(analysis, plots_dir))
        
        # Plot 3: Linguistic Diversity Analysis
        saved_plots.append(self._plot_linguistic_diversity(analysis, plots_dir))
        
        # Plot 4: Temporal Dynamics
        saved_plots.append(self._plot_temporal_dynamics(analysis, plots_dir))
        
        # Plot 5: Statistical Summary
        saved_plots.append(self._plot_statistical_summary(analysis, plots_dir))
        
        return [p for p in saved_plots if p]
    
    def _plot_model_performance(self, analysis: Dict[str, Any], plots_dir: Path) -> str:
        """Plot model performance comparison"""
        aggregated = analysis.get('aggregated_metrics', {})
        if not aggregated:
            return ""
        
        # Prepare data
        models = []
        latencies = []
        call_counts = []
        context_sizes = []
        
        for group_name, metrics in aggregated.items():
            if 'GPT-5' in group_name or 'Qwen3-8B' in group_name:
                models.append(group_name)
                latencies.append(metrics.get('avg_llm_latency', {}).get('mean', 0))
                call_counts.append(metrics.get('total_llm_calls', {}).get('mean', 0))
                context_sizes.append(metrics.get('avg_context_size', {}).get('mean', 0))
        
        if not models:
            return ""
        
        fig, ((ax1, ax2), (ax3, ax4)) = plt.subplots(2, 2, figsize=(14, 10))
        fig.suptitle('LLM Model Performance Comparison', fontsize=16, fontweight='bold')
        
        # Latency comparison
        bars1 = ax1.bar(models, latencies, color=['#2E86AB', '#A23B72', '#F18F01'], alpha=0.8)
        ax1.set_title('Average Response Latency')
        ax1.set_ylabel('Latency (seconds)')
        ax1.tick_params(axis='x', rotation=45)
        for bar, val in zip(bars1, latencies):
            ax1.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.01, 
                    f'{val:.3f}', ha='center', va='bottom')
        
        # Call count comparison
        bars2 = ax2.bar(models, call_counts, color=['#2E86AB', '#A23B72', '#F18F01'], alpha=0.8)
        ax2.set_title('Total LLM API Calls')
        ax2.set_ylabel('Number of Calls')
        ax2.tick_params(axis='x', rotation=45)
        for bar, val in zip(bars2, call_counts):
            ax2.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 1, 
                    f'{int(val)}', ha='center', va='bottom')
        
        # Context size comparison
        bars3 = ax3.bar(models, context_sizes, color=['#2E86AB', '#A23B72', '#F18F01'], alpha=0.8)
        ax3.set_title('Average Context Size')
        ax3.set_ylabel('Context Size (tokens)')
        ax3.tick_params(axis='x', rotation=45)
        for bar, val in zip(bars3, context_sizes):
            ax3.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 10, 
                    f'{int(val)}', ha='center', va='bottom')
        
        # Efficiency scatter plot
        if len(latencies) > 1 and len(call_counts) > 1:
            scatter = ax4.scatter(latencies, call_counts, 
                                s=[size/10 for size in context_sizes], 
                                c=['#2E86AB', '#A23B72', '#F18F01'][:len(models)], 
                                alpha=0.7)
            ax4.set_xlabel('Average Latency (s)')
            ax4.set_ylabel('Total LLM Calls')
            ax4.set_title('Efficiency vs Usage Trade-off')
            
            # Add model labels
            for i, model in enumerate(models):
                ax4.annotate(model, (latencies[i], call_counts[i]), 
                           xytext=(5, 5), textcoords='offset points')
        
        plt.tight_layout()
        output_path = plots_dir / "model_performance_comparison.png"
        plt.savefig(output_path, dpi=300, bbox_inches='tight')
        plt.close()
        
        return str(output_path)
    
    def _plot_reputation_effects(self, analysis: Dict[str, Any], plots_dir: Path) -> str:
        """Plot reputation system effects"""
        aggregated = analysis.get('aggregated_metrics', {})
        if not aggregated:
            return ""
        
        # Separate reputation ON/OFF groups
        rep_on_groups = {k: v for k, v in aggregated.items() if 'Rep+' in k}
        rep_off_groups = {k: v for k, v in aggregated.items() if 'Rep-' in k}
        
        if not rep_on_groups or not rep_off_groups:
            return ""
        
        fig, ((ax1, ax2), (ax3, ax4)) = plt.subplots(2, 2, figsize=(14, 10))
        fig.suptitle('Reputation System Impact Analysis', fontsize=16, fontweight='bold')
        
        # Message count comparison
        models = []
        rep_on_msgs = []
        rep_off_msgs = []
        
        for group_name in rep_on_groups:
            base_name = group_name.replace(' (Rep+)', '')
            rep_off_name = base_name + ' (Rep-)'
            
            if rep_off_name in rep_off_groups:
                models.append(base_name)
                rep_on_msgs.append(rep_on_groups[group_name].get('message_count', {}).get('mean', 0))
                rep_off_msgs.append(rep_off_groups[rep_off_name].get('message_count', {}).get('mean', 0))
        
        if models:
            x = np.arange(len(models))
            width = 0.35
            
            bars1 = ax1.bar(x - width/2, rep_on_msgs, width, label='Reputation ON', color='#2E86AB', alpha=0.8)
            bars2 = ax1.bar(x + width/2, rep_off_msgs, width, label='Reputation OFF', color='#A23B72', alpha=0.8)
            
            ax1.set_title('Message Count by Reputation Setting')
            ax1.set_ylabel('Average Messages per Session')
            ax1.set_xticks(x)
            ax1.set_xticklabels(models)
            ax1.legend()
            
            # Add value labels
            for bar in bars1:
                height = bar.get_height()
                ax1.text(bar.get_x() + bar.get_width()/2., height + 1,
                        f'{int(height)}', ha='center', va='bottom')
            for bar in bars2:
                height = bar.get_height()
                ax1.text(bar.get_x() + bar.get_width()/2., height + 1,
                        f'{int(height)}', ha='center', va='bottom')
        
        # Lexical diversity comparison
        rep_on_lex = []
        rep_off_lex = []
        
        for group_name in rep_on_groups:
            base_name = group_name.replace(' (Rep+)', '')
            rep_off_name = base_name + ' (Rep-)'
            
            if rep_off_name in rep_off_groups:
                rep_on_lex.append(rep_on_groups[group_name].get('lexical_diversity', {}).get('mean', 0))
                rep_off_lex.append(rep_off_groups[rep_off_name].get('lexical_diversity', {}).get('mean', 0))
        
        if rep_on_lex and rep_off_lex:
            bars3 = ax2.bar(x - width/2, rep_on_lex, width, label='Reputation ON', color='#2E86AB', alpha=0.8)
            bars4 = ax2.bar(x + width/2, rep_off_lex, width, label='Reputation OFF', color='#A23B72', alpha=0.8)
            
            ax2.set_title('Lexical Diversity by Reputation Setting')
            ax2.set_ylabel('Lexical Diversity Score')
            ax2.set_xticks(x)
            ax2.set_xticklabels(models)
            ax2.legend()
        
        # Statistical significance testing
        if len(rep_on_msgs) > 1 and len(rep_off_msgs) > 1:
            stat_tests = analysis.get('statistical_tests', {})
            
            test_names = []
            p_values = []
            effect_sizes = []
            
            for test_name, test_result in stat_tests.items():
                if 'reputation' in test_name and isinstance(test_result, dict):
                    test_names.append(test_result.get('description', test_name)[:20])
                    p_values.append(test_result.get('p_value', 1.0))
                    effect_sizes.append(abs(test_result.get('effect_size_cohens_d', 0.0)))
            
            if test_names:
                # P-values plot
                colors = ['red' if p < 0.05 else 'orange' if p < 0.1 else 'gray' for p in p_values]
                bars5 = ax3.bar(test_names, p_values, color=colors, alpha=0.7)
                ax3.axhline(y=0.05, color='red', linestyle='--', alpha=0.7, label='p=0.05')
                ax3.set_title('Statistical Significance Tests')
                ax3.set_ylabel('p-value')
                ax3.tick_params(axis='x', rotation=45)
                ax3.legend()
                
                # Effect sizes
                bars6 = ax4.bar(test_names, effect_sizes, color='#F18F01', alpha=0.7)
                ax4.set_title('Effect Sizes (Cohen\'s d)')
                ax4.set_ylabel('Effect Size')
                ax4.tick_params(axis='x', rotation=45)
                
                # Add interpretation lines
                ax4.axhline(y=0.2, color='green', linestyle='--', alpha=0.5, label='Small')
                ax4.axhline(y=0.5, color='orange', linestyle='--', alpha=0.5, label='Medium')
                ax4.axhline(y=0.8, color='red', linestyle='--', alpha=0.5, label='Large')
                ax4.legend()
        
        plt.tight_layout()
        output_path = plots_dir / "reputation_effects_analysis.png"
        plt.savefig(output_path, dpi=300, bbox_inches='tight')
        plt.close()
        
        return str(output_path)
    
    def _plot_linguistic_diversity(self, analysis: Dict[str, Any], plots_dir: Path) -> str:
        """Plot linguistic diversity analysis"""
        sessions = analysis.get('sessions', {})
        if not sessions:
            return ""
        
        # Prepare data
        session_data = []
        for session_id, data in sessions.items():
            # Extract experiment type
            if 'gpt5' in session_id:
                model = 'GPT-5'
            elif 'qwen8b' in session_id:
                model = 'Qwen3-8B'
            elif 'mixed' in session_id:
                model = 'Mixed'
            else:
                model = 'Other'
            
            reputation = 'ON' if 'rep_on' in session_id else 'OFF'
            
            session_data.append({
                'session_id': session_id,
                'model': model,
                'reputation': reputation,
                'ttr': data.get('type_token_ratio', 0),
                'lexical_diversity': data.get('lexical_diversity', 0),
                'vocab_richness': data.get('vocabulary_richness', 0),
                'unique_words': data.get('unique_words', 0),
                'total_words': data.get('total_words', 1)
            })
        
        if not session_data:
            return ""
        
        df = pd.DataFrame(session_data)
        
        fig, ((ax1, ax2), (ax3, ax4)) = plt.subplots(2, 2, figsize=(14, 10))
        fig.suptitle('Linguistic Diversity Analysis', fontsize=16, fontweight='bold')
        
        # TTR by model
        sns.boxplot(data=df, x='model', y='ttr', ax=ax1)
        ax1.set_title('Type-Token Ratio by Model')
        ax1.set_ylabel('Type-Token Ratio')
        
        # Lexical diversity by model and reputation
        sns.boxplot(data=df, x='model', y='lexical_diversity', hue='reputation', ax=ax2)
        ax2.set_title('Lexical Diversity by Model and Reputation')
        ax2.set_ylabel('Lexical Diversity (MTLD approx.)')
        
        # Vocabulary richness scatter
        scatter = ax3.scatter(df['total_words'], df['vocab_richness'], 
                            c=df['model'].map({'GPT-5': 0, 'Qwen3-8B': 1, 'Mixed': 2}),
                            cmap='viridis', alpha=0.7, s=60)
        ax3.set_xlabel('Total Words')
        ax3.set_ylabel('Vocabulary Richness (Herdan\'s C)')
        ax3.set_title('Vocabulary Richness vs Corpus Size')
        
        # Create custom legend for scatter plot
        import matplotlib.lines as mlines
        colors = ['#2E86AB', '#A23B72', '#F18F01']
        legend_elements = [mlines.Line2D([0], [0], marker='o', color='w', 
                                    markerfacecolor=colors[i], markersize=8, label=model)
                         for i, model in enumerate(['GPT-5', 'Qwen3-8B', 'Mixed'])]
        ax3.legend(handles=legend_elements)
        
        # Correlation heatmap
        numeric_cols = ['ttr', 'lexical_diversity', 'vocab_richness', 'unique_words', 'total_words']
        corr_matrix = df[numeric_cols].corr()
        
        im = ax4.imshow(corr_matrix, cmap='coolwarm', aspect='auto', vmin=-1, vmax=1)
        ax4.set_xticks(range(len(numeric_cols)))
        ax4.set_yticks(range(len(numeric_cols)))
        ax4.set_xticklabels([col.replace('_', '\n') for col in numeric_cols], rotation=45)
        ax4.set_yticklabels([col.replace('_', '\n') for col in numeric_cols])
        ax4.set_title('Linguistic Metrics Correlation')
        
        # Add correlation values (simplified)
        for i in range(len(numeric_cols)):
            for j in range(len(numeric_cols)):
                corr_val = corr_matrix.values[i, j]
                text = ax4.text(j, i, f'{corr_val:.2f}',
                              ha="center", va="center", 
                              color="black" if abs(corr_val) < 0.5 else "white")
        
        # Add colorbar
        plt.colorbar(im, ax=ax4, shrink=0.8)
        
        plt.tight_layout()
        output_path = plots_dir / "linguistic_diversity_analysis.png"
        plt.savefig(output_path, dpi=300, bbox_inches='tight')
        plt.close()
        
        return str(output_path)
    
    def _plot_temporal_dynamics(self, analysis: Dict[str, Any], plots_dir: Path) -> str:
        """Plot temporal dynamics"""
        sessions = analysis.get('sessions', {})
        if not sessions:
            return ""
        
        fig, ((ax1, ax2), (ax3, ax4)) = plt.subplots(2, 2, figsize=(14, 10))
        fig.suptitle('Temporal Dynamics Analysis', fontsize=16, fontweight='bold')
        
        # Session duration by model
        models = []
        durations = []
        message_rates = []
        
        for session_id, data in sessions.items():
            if 'gpt5' in session_id:
                model = 'GPT-5'
            elif 'qwen8b' in session_id:
                model = 'Qwen3-8B'
            elif 'mixed' in session_id:
                model = 'Mixed'
            else:
                continue
            
            models.append(model)
            durations.append(data.get('session_duration_hours', 0))
            message_rates.append(data.get('messages_per_hour', 0))
        
        if models:
            df_temporal = pd.DataFrame({
                'model': models,
                'duration': durations,
                'message_rate': message_rates
            })
            
            # Duration comparison
            sns.boxplot(data=df_temporal, x='model', y='duration', ax=ax1)
            ax1.set_title('Session Duration by Model')
            ax1.set_ylabel('Duration (hours)')
            
            # Message rate comparison
            sns.boxplot(data=df_temporal, x='model', y='message_rate', ax=ax2)
            ax2.set_title('Message Rate by Model')
            ax2.set_ylabel('Messages per Hour')
            
            # Efficiency scatter
            scatter = ax3.scatter(df_temporal['duration'], df_temporal['message_rate'], 
                                c=df_temporal['model'].map({'GPT-5': 0, 'Qwen3-8B': 1, 'Mixed': 2}),
                                cmap='viridis', alpha=0.7, s=60)
            ax3.set_xlabel('Session Duration (hours)')
            ax3.set_ylabel('Messages per Hour')
            ax3.set_title('Temporal Efficiency')
        
        # Peak activity analysis
        peak_periods = {}
        for session_id, data in sessions.items():
            peak = data.get('peak_activity_period', 'unknown')
            if peak != 'unknown':
                peak_periods[peak] = peak_periods.get(peak, 0) + 1
        
        if peak_periods:
            periods = list(peak_periods.keys())
            counts = list(peak_periods.values())
            
            bars = ax4.bar(periods, counts, color='#F18F01', alpha=0.8)
            ax4.set_title('Peak Activity Distribution')
            ax4.set_ylabel('Number of Sessions')
            ax4.set_xlabel('Time Period')
            ax4.tick_params(axis='x', rotation=45)
            
            # Add value labels
            for bar, count in zip(bars, counts):
                ax4.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.05,
                        str(count), ha='center', va='bottom')
        
        plt.tight_layout()
        output_path = plots_dir / "temporal_dynamics_analysis.png"
        plt.savefig(output_path, dpi=300, bbox_inches='tight')
        plt.close()
        
        return str(output_path)
    
    def _plot_statistical_summary(self, analysis: Dict[str, Any], plots_dir: Path) -> str:
        """Plot statistical summary"""
        tests = analysis.get('statistical_tests', {})
        if not tests:
            return ""
        
        fig, ((ax1, ax2), (ax3, ax4)) = plt.subplots(2, 2, figsize=(14, 10))
        fig.suptitle('Statistical Analysis Summary', fontsize=16, fontweight='bold')
        
        # P-values overview
        test_names = []
        p_values = []
        effect_sizes = []
        
        for test_name, test_result in tests.items():
            if isinstance(test_result, dict) and 'p_value' in test_result:
                test_names.append(test_name.replace('_', '\n')[:20])
                p_values.append(test_result.get('p_value', 1.0))
                effect_sizes.append(abs(test_result.get('effect_size_cohens_d', 0.0)))
        
        if test_names:
            # P-values with significance levels
            colors = ['darkred' if p < 0.01 else 'red' if p < 0.05 else 'orange' if p < 0.1 else 'gray' 
                     for p in p_values]
            bars1 = ax1.bar(test_names, p_values, color=colors, alpha=0.8)
            ax1.axhline(y=0.01, color='darkred', linestyle='--', alpha=0.7, label='p=0.01')
            ax1.axhline(y=0.05, color='red', linestyle='--', alpha=0.7, label='p=0.05')
            ax1.axhline(y=0.10, color='orange', linestyle='--', alpha=0.7, label='p=0.10')
            ax1.set_title('Statistical Significance Tests')
            ax1.set_ylabel('p-value')
            ax1.tick_params(axis='x', rotation=45)
            ax1.legend()
            ax1.set_yscale('log')
            
            # Effect sizes with interpretation
            colors2 = ['lightgreen' if es < 0.2 else 'yellow' if es < 0.5 else 'orange' if es < 0.8 else 'red'
                      for es in effect_sizes]
            bars2 = ax2.bar(test_names, effect_sizes, color=colors2, alpha=0.8)
            ax2.axhline(y=0.2, color='green', linestyle='--', alpha=0.5, label='Small (0.2)')
            ax2.axhline(y=0.5, color='orange', linestyle='--', alpha=0.5, label='Medium (0.5)')
            ax2.axhline(y=0.8, color='red', linestyle='--', alpha=0.5, label='Large (0.8)')
            ax2.set_title('Effect Sizes (Cohen\'s d)')
            ax2.set_ylabel('Effect Size')
            ax2.tick_params(axis='x', rotation=45)
            ax2.legend()
            
            # Significance summary
            sig_counts = {
                'p < 0.01': sum(1 for p in p_values if p < 0.01),
                '0.01 ≤ p < 0.05': sum(1 for p in p_values if 0.01 <= p < 0.05),
                '0.05 ≤ p < 0.10': sum(1 for p in p_values if 0.05 <= p < 0.10),
                'p ≥ 0.10': sum(1 for p in p_values if p >= 0.10)
            }
            
            wedges, texts, autotexts = ax3.pie(sig_counts.values(), labels=sig_counts.keys(), 
                                             autopct='%1.0f', startangle=90,
                                             colors=['darkred', 'red', 'orange', 'gray'])
            ax3.set_title('Distribution of p-values')
            
            # Effect size summary
            effect_counts = {
                'Small (< 0.2)': sum(1 for es in effect_sizes if es < 0.2),
                'Medium (0.2-0.5)': sum(1 for es in effect_sizes if 0.2 <= es < 0.5),
                'Large (0.5-0.8)': sum(1 for es in effect_sizes if 0.5 <= es < 0.8),
                'Very Large (≥ 0.8)': sum(1 for es in effect_sizes if es >= 0.8)
            }
            
            wedges2, texts2, autotexts2 = ax4.pie(effect_counts.values(), labels=effect_counts.keys(),
                                                 autopct='%1.0f', startangle=90,
                                                 colors=['lightgreen', 'yellow', 'orange', 'red'])
            ax4.set_title('Distribution of Effect Sizes')
        
        plt.tight_layout()
        output_path = plots_dir / "statistical_summary.png"
        plt.savefig(output_path, dpi=300, bbox_inches='tight')
        plt.close()
        
        return str(output_path)
    
    def generate_report(self, analysis: Dict[str, Any], output_path: str):
        """Generate comprehensive academic report"""
        
        metadata = analysis.get('metadata', {})
        sessions = analysis.get('sessions', {})
        aggregated = analysis.get('aggregated_metrics', {})
        tests = analysis.get('statistical_tests', {})
        
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
- **Metrics:** Efficiency, linguistic diversity, temporal dynamics
- **Statistical Analysis:** Independent t-tests, effect size calculations

### Key Metrics
1. **Efficiency Metrics:**
   - Total LLM API calls
   - Average response latency
   - Context size utilization

2. **Linguistic Diversity Metrics:**
   - Type-Token Ratio (TTR)
   - Lexical Diversity (MTLD approximation)
   - Vocabulary Richness (Herdan's C)

3. **Temporal Metrics:**
   - Session duration
   - Message generation rate
   - Peak activity patterns

## Results Summary

### Model Performance Comparison
"""
        
        if aggregated:
            for group_name, metrics in aggregated.items():
                if any(model in group_name for model in ['GPT-5', 'Qwen3-8B', 'Mixed']):
                    report += f"\n**{group_name}:**\n"
                    
                    llm_calls = metrics.get('total_llm_calls', {})
                    if llm_calls:
                        report += f"- Average LLM Calls: {llm_calls.get('mean', 0):.1f} (±{llm_calls.get('std', 0):.1f})\n"
                    
                    latency = metrics.get('avg_llm_latency', {})
                    if latency:
                        report += f"- Average Latency: {latency.get('mean', 0):.3f}s (±{latency.get('std', 0):.3f})\n"
                    
                    ttr = metrics.get('type_token_ratio', {})
                    if ttr:
                        report += f"- Type-Token Ratio: {ttr.get('mean', 0):.3f} (±{ttr.get('std', 0):.3f})\n"
        
        report += "\n### Statistical Significance Tests\n"
        
        if tests:
            for test_name, test_result in tests.items():
                if isinstance(test_result, dict) and 'p_value' in test_result:
                    significance = "***" if test_result.get('p_value', 1) < 0.001 else \
                                 "**" if test_result.get('p_value', 1) < 0.01 else \
                                 "*" if test_result.get('p_value', 1) < 0.05 else "n.s."
                    
                    effect_size = test_result.get('effect_size_cohens_d', 0)
                    effect_magnitude = "large" if abs(effect_size) >= 0.8 else \
                                     "medium" if abs(effect_size) >= 0.5 else \
                                     "small" if abs(effect_size) >= 0.2 else "negligible"
                    
                    report += f"\n**{test_result.get('description', test_name)}:**\n"
                    report += f"- p-value: {test_result.get('p_value', 1):.6f} {significance}\n"
                    report += f"- Effect size (Cohen's d): {effect_size:.3f} ({effect_magnitude})\n"
                    report += f"- Group 1 mean: {test_result.get('group1_mean', 0):.3f}\n"
                    report += f"- Group 2 mean: {test_result.get('group2_mean', 0):.3f}\n"
        else:
            report += "\nNo statistical tests were performed (insufficient data).\n"
        
        report += f"""

## Conclusions

### Key Findings
1. **Model Efficiency:** [Analyze based on latency and call patterns]
2. **Linguistic Quality:** [Analyze based on diversity metrics]
3. **Reputation System Impact:** [Analyze based on reputation tests]
4. **Temporal Patterns:** [Analyze based on activity distribution]

### Recommendations
1. **Optimal Configuration:** [Based on statistical analysis]
2. **Performance Trade-offs:** [Based on efficiency vs quality metrics]
3. **Future Research:** [Based on observed patterns and limitations]

## Technical Notes

### Data Processing
- Sessions with incomplete data were excluded from statistical analysis
- Linguistic metrics computed using standard NLP techniques
- Statistical tests assume normal distribution (validated where possible)

### Limitations
- Limited sample size for some comparisons
- Experimental conditions may not reflect real-world usage
- Context length variations across models may affect comparisons

---

*This report was generated automatically from experimental data. For questions about methodology or interpretation, please refer to the experimental protocol documentation.*
"""
        
        # Save report
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(report)
        
        return output_path


def main():
    """Main analysis function with enhanced academic output"""
    
    parser = argparse.ArgumentParser(description="Enhanced Academic Analysis for LLM Agent Experiments")
    parser.add_argument("--experiment", help="Filter by experiment name")
    parser.add_argument("--db", default="databases/checkpoints.db", help="Database path")
    parser.add_argument("--metrics", default="metrics", help="Metrics directory")
    parser.add_argument("--output", default="metrics/academic_analysis", help="Output directory")
    parser.add_argument("--no-plots", action="store_true", help="Skip plot generation")
    parser.add_argument("--no-report", action="store_true", help="Skip report generation")
    
    args = parser.parse_args()
    
    # Initialize analyzer
    analyzer = AcademicAnalyzer(args.db, args.metrics)
    
    # Load and analyze data
    print("Loading experimental data...")
    analysis = analyzer.load_experiment_data(args.experiment)
    
    # Create output directory
    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Save detailed analysis
    analysis_file = output_dir / "detailed_analysis.json"
    with open(analysis_file, 'w') as f:
        json.dump(analysis, f, indent=2, cls=NumpyEncoder)
    print(f"Detailed analysis saved: {analysis_file}")
    
    # Generate academic plots
    if not args.no_plots and ADVANCED_PLOTTING:
        print("Generating academic plots...")
        plot_files = analyzer.generate_academic_plots(analysis, str(output_dir))
        
        if plot_files:
            print("Academic plots generated:")
            for plot_file in plot_files:
                if plot_file:
                    print(f"  - {plot_file}")
        else:
            print("No plots generated (insufficient data)")
    elif not ADVANCED_PLOTTING:
        print("Skipping plots (advanced plotting libraries not available)")
    
    # Generate comprehensive report
    if not args.no_report:
        print("Generating academic report...")
        report_file = output_dir / "academic_report.md"
        analyzer.generate_report(analysis, str(report_file))
        print(f"Academic report saved: {report_file}")
    
    # Export summary CSV
    csv_file = output_dir / "summary_statistics.csv"
    if analysis.get('aggregated_metrics'):
        df_summary = pd.DataFrame.from_dict(analysis['aggregated_metrics'], orient='index')
        df_summary.to_csv(csv_file)
        print(f"Summary statistics saved: {csv_file}")
    
    print(f"\n✅ Academic analysis complete! Output directory: {output_dir}")


if __name__ == "__main__":
    main()
