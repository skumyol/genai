import time
import json
import csv
import os
import threading
from datetime import datetime
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, asdict
import logging

logger = logging.getLogger(__name__)

@dataclass
class MetricEntry:
    timestamp: str
    metric_type: str
    value: float
    context: Dict[str, Any]
    session_id: str
    experiment_id: str

class MetricsCollector:
    def __init__(self, experiment_id: str, session_id: str, output_dir: str = "metrics"):
        self.experiment_id = experiment_id
        self.session_id = session_id
        self.output_dir = output_dir
        self.metrics: List[MetricEntry] = []
        # Use reentrant lock because record_llm_call calls record_metric internally.
        # A non-reentrant Lock would deadlock when record_metric tries to acquire it again.
        self.lock = threading.RLock()
        self.start_time = time.time()
        
        # Ensure output directory exists
        os.makedirs(output_dir, exist_ok=True)
        
        # Initialize CSV files
        self.csv_file = os.path.join(output_dir, f"{experiment_id}_{session_id}_metrics.csv")
        self.json_file = os.path.join(output_dir, f"{experiment_id}_{session_id}_metrics.json")
        
        # LLM call tracking
        self.llm_calls = {
            "total_calls": 0,
            "calls_by_agent": {},
            "calls_by_model": {},
            "context_sizes": [],
            "latencies": []
        }
        
        # Initialize CSV header
        self._init_csv()
        
    def _init_csv(self):
        """Initialize CSV file with headers"""
        with open(self.csv_file, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow([
                'timestamp', 'metric_type', 'value', 'context', 
                'session_id', 'experiment_id', 'elapsed_time'
            ])
    
    def record_metric(self, metric_type: str, value: float, context: Dict[str, Any] = None):
        """Record a metric entry"""
        with self.lock:
            entry = MetricEntry(
                timestamp=datetime.utcnow().isoformat(),
                metric_type=metric_type,
                value=value,
                context=context or {},
                session_id=self.session_id,
                experiment_id=self.experiment_id
            )
            self.metrics.append(entry)
            
            # Write to CSV immediately for real-time monitoring
            with open(self.csv_file, 'a', newline='') as f:
                writer = csv.writer(f)
                writer.writerow([
                    entry.timestamp,
                    entry.metric_type,
                    entry.value,
                    json.dumps(entry.context),
                    entry.session_id,
                    entry.experiment_id,
                    time.time() - self.start_time
                ])
    
    def record_llm_call(self, agent_name: str, model: str, prompt_tokens: int, 
                       completion_tokens: int, latency: float, context: Dict[str, Any] = None):
        """Record LLM call metrics"""
        with self.lock:
            self.llm_calls["total_calls"] += 1
            
            # Track by agent
            if agent_name not in self.llm_calls["calls_by_agent"]:
                self.llm_calls["calls_by_agent"][agent_name] = 0
            self.llm_calls["calls_by_agent"][agent_name] += 1
            
            # Track by model
            if model not in self.llm_calls["calls_by_model"]:
                self.llm_calls["calls_by_model"][model] = 0
            self.llm_calls["calls_by_model"][model] += 1
            
            # Track context sizes and latencies
            total_tokens = prompt_tokens + completion_tokens
            self.llm_calls["context_sizes"].append(total_tokens)
            self.llm_calls["latencies"].append(latency)
            
            # Record individual metrics
            self.record_metric("llm_call_latency", latency, {
                "agent": agent_name,
                "model": model,
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "total_tokens": total_tokens,
                **context
            })
            
            self.record_metric("llm_context_size", total_tokens, {
                "agent": agent_name,
                "model": model,
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens
            })
    
    def record_dialogue_metrics(self, initiator: str, receiver: str, 
                              message_count: int, total_latency: float,
                              reputation_update_latency: Optional[float] = None):
        """Record dialogue-specific metrics"""
        context = {
            "initiator": initiator,
            "receiver": receiver,
            "message_count": message_count
        }
        
        self.record_metric("dialogue_total_latency", total_latency, context)
        self.record_metric("dialogue_message_count", message_count, context)
        
        if reputation_update_latency is not None:
            self.record_metric("reputation_update_latency", reputation_update_latency, context)
    
    def get_summary_stats(self) -> Dict[str, Any]:
        """Get summary statistics"""
        with self.lock:
            elapsed_time = time.time() - self.start_time
            
            # Calculate latency stats
            latencies = [m.value for m in self.metrics if m.metric_type.endswith('_latency')]
            context_sizes = [m.value for m in self.metrics if m.metric_type == 'llm_context_size']
            
            return {
                "experiment_id": self.experiment_id,
                "session_id": self.session_id,
                "elapsed_time": elapsed_time,
                "total_metrics": len(self.metrics),
                "llm_stats": {
                    "total_calls": self.llm_calls["total_calls"],
                    "calls_by_agent": self.llm_calls["calls_by_agent"],
                    "calls_by_model": self.llm_calls["calls_by_model"],
                    "avg_latency": sum(latencies) / len(latencies) if latencies else 0,
                    "avg_context_size": sum(context_sizes) / len(context_sizes) if context_sizes else 0,
                    "max_context_size": max(context_sizes) if context_sizes else 0
                },
                "metrics_by_type": self._get_metrics_by_type()
            }
    
    def _get_metrics_by_type(self) -> Dict[str, Dict[str, float]]:
        """Group metrics by type with basic stats"""
        by_type = {}
        for metric in self.metrics:
            if metric.metric_type not in by_type:
                by_type[metric.metric_type] = []
            by_type[metric.metric_type].append(metric.value)
        
        stats = {}
        for metric_type, values in by_type.items():
            stats[metric_type] = {
                "count": len(values),
                "avg": sum(values) / len(values),
                "min": min(values),
                "max": max(values)
            }
        
        return stats
    
    def export_json(self):
        """Export all metrics to JSON"""
        with self.lock:
            data = {
                "experiment_id": self.experiment_id,
                "session_id": self.session_id,
                "start_time": self.start_time,
                "export_time": time.time(),
                "summary": self.get_summary_stats(),
                "metrics": [asdict(m) for m in self.metrics]
            }
            
            with open(self.json_file, 'w') as f:
                json.dump(data, f, indent=2)
    
    def log_periodic_summary(self):
        """Log periodic summary for monitoring"""
        stats = self.get_summary_stats()
        logger.info(
            "METRICS SUMMARY | experiment=%s session=%s elapsed=%.1fs "
            "total_metrics=%d llm_calls=%d avg_latency=%.3fs avg_context=%d",
            self.experiment_id,
            self.session_id,
            stats["elapsed_time"],
            stats["total_metrics"],
            stats["llm_stats"]["total_calls"],
            stats["llm_stats"]["avg_latency"],
            stats["llm_stats"]["avg_context_size"]
        )

# Global metrics collector instance
_metrics_collector: Optional[MetricsCollector] = None

def init_metrics_collector(experiment_id: str, session_id: str) -> MetricsCollector:
    """Initialize global metrics collector"""
    global _metrics_collector
    _metrics_collector = MetricsCollector(experiment_id, session_id)
    return _metrics_collector

def get_metrics_collector() -> Optional[MetricsCollector]:
    """Get current metrics collector"""
    return _metrics_collector

def record_metric(metric_type: str, value: float, context: Dict[str, Any] = None):
    """Convenience function to record metric"""
    if _metrics_collector:
        _metrics_collector.record_metric(metric_type, value, context)

def record_llm_call(agent_name: str, model: str, prompt_tokens: int, 
                   completion_tokens: int, latency: float, context: Dict[str, Any] = None):
    """Convenience function to record LLM call"""
    if _metrics_collector:
        _metrics_collector.record_llm_call(agent_name, model, prompt_tokens, 
                                         completion_tokens, latency, context)
