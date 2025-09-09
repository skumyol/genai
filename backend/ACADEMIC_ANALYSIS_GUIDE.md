# Academic Analysis Guide for LLM Agent Experiments

## Overview

The enhanced academic analysis system provides publication-quality plots, comprehensive statistical analysis, and structured academic reports for your LLM agent experiments.

## Quick Start

### 1. Basic Academic Analysis

Generate a comprehensive academic analysis with publication-ready plots:

```bash
python simple_academic_analyzer.py
```

### 2. Filtered Analysis

Analyze specific experiments:

```bash
python simple_academic_analyzer.py --experiment "gpt5"
python simple_academic_analyzer.py --experiment "qwen"
```

### 3. Enhanced Standard Plots

Generate enhanced versions of the standard analysis plots:

```bash
python analyze_experiments.py
```

## Output Files

### Academic Analysis Directory Structure
```
metrics/academic_analysis_YYYYMMDD_HHMMSS/
├── academic_report.md              # Structured academic report
├── detailed_analysis.json          # Comprehensive data analysis
├── summary_statistics.csv          # Statistical summaries
└── academic_plots/
    ├── message_count_comparison.png
    ├── linguistic_diversity_analysis.png
    └── group_comparison_analysis.png
```

### Enhanced Standard Plots
```
metrics/plots/
├── academic_avg_total_llm_calls.png
├── academic_avg_llm_latency.png
├── academic_avg_context_size.png
├── academic_avg_ttr.png
├── academic_avg_unique_message_ratio.png
└── academic_comprehensive_analysis.png
```

## Key Features

### 📊 Publication-Ready Plots
- **High Resolution**: 300 DPI for print quality
- **Professional Typography**: Academic-standard fonts and sizing
- **Color Schemes**: Colorblind-friendly palettes
- **Clean Layout**: Proper spacing and grid lines

### 📈 Statistical Analysis
- **Type-Token Ratio (TTR)**: Linguistic diversity measurement
- **Vocabulary Richness**: Herdan's C metric for lexical diversity
- **Effect Sizes**: Cohen's d for practical significance
- **Confidence Intervals**: Statistical uncertainty quantification

### 📋 Academic Reports
- **Methodology Section**: Clear experimental design description
- **Results Summary**: Quantitative findings with statistics
- **Technical Notes**: Data processing and limitations
- **Conclusions**: Research insights and recommendations

## Metrics Explained

### Communication Metrics
- **Message Count**: Total messages generated per session
- **Dialogue Count**: Number of conversation threads
- **Unique Speakers**: Distinct participants in conversations

### Linguistic Quality Metrics
- **Type-Token Ratio (TTR)**: Unique words / Total words
  - Higher values indicate greater lexical diversity
  - Range: 0.0 to 1.0
  
- **Vocabulary Richness (Herdan's C)**: log(unique_words) / log(total_words)
  - Measures vocabulary sophistication
  - Less sensitive to text length than TTR

### Efficiency Metrics
- **LLM Latency**: Average response time per API call
- **Context Size**: Average tokens used per request
- **Total LLM Calls**: API usage frequency

## Advanced Usage

### Custom Analysis
```bash
# Specific output directory
python simple_academic_analyzer.py --output "results/my_analysis"

# Skip plots (data only)
python simple_academic_analyzer.py --no-plots

# Skip report generation
python simple_academic_analyzer.py --no-report
```

### Data Export
```bash
# Enhanced standard analysis with CSV export
python analyze_experiments.py --csv "my_results.csv"

# JSON output for programmatic analysis
python analyze_experiments.py --out "detailed_results.json"
```

## Integration with Research Workflow

### For Presentations
1. Use `academic_comprehensive_analysis.png` for overview slides
2. Use individual metric plots for detailed analysis
3. Include statistical summaries from CSV files

### For Publications
1. Reference the academic report for methodology descriptions
2. Use 300 DPI plots directly in manuscripts
3. Include effect sizes and confidence intervals from JSON data

### For Further Analysis
1. Import CSV files into R/Python for additional statistics
2. Use JSON data for meta-analysis across experiments
3. Combine results with external datasets

## Troubleshooting

### Common Issues

**No plots generated**: Check that matplotlib and seaborn are installed
```bash
pip install matplotlib seaborn pandas numpy scipy
```

**Empty analysis**: Verify database path and experiment naming
```bash
# Check available sessions
python -c "from database_manager import DatabaseManager; db = DatabaseManager('databases/checkpoints.db'); print([row[0] for row in db.get_connection().execute('SELECT session_id FROM sessions LIMIT 5')])"
```

**Memory issues**: Use filtering for large datasets
```bash
python simple_academic_analyzer.py --experiment "specific_model"
```

## Best Practices

### Experiment Design
- Use consistent naming conventions for sessions
- Include control conditions (reputation on/off)
- Document experimental parameters in session metadata

### Analysis Workflow
1. Run full analysis first to understand data
2. Generate filtered analyses for specific comparisons
3. Create custom visualizations for unique insights
4. Document methodology in academic reports

### Quality Assurance
- Review statistical significance before interpreting results
- Check effect sizes for practical significance
- Validate assumptions (normality, independence)
- Consider multiple comparison corrections

---

*This guide covers the enhanced academic analysis system. For basic experiment analysis, see the standard `analyze_experiments.py` documentation.*
