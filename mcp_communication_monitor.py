#!/usr/bin/env python3
"""
MCP Server Communication Monitor

This script monitors the communication health of the MCP server and can help
identify when communication failures occur.
"""

import asyncio
import time
import logging
import json
from pathlib import Path
import sys
from typing import Dict, List, Optional
from dataclasses import dataclass, asdict
from datetime import datetime

# Add the src directory to the path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from serena.async_tool_executor import AsyncToolExecutor, UnifiedToolDispatcher, HealthChecker

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('mcp_communication_monitor.log')
    ]
)

log = logging.getLogger(__name__)


@dataclass
class HealthSnapshot:
    """Represents a health check snapshot."""
    timestamp: float
    datetime_str: str
    ping_success: bool
    ping_duration_ms: float
    executor_stats: Dict
    overall_status: str
    error: Optional[str] = None


class CommunicationMonitor:
    """
    Monitors MCP server communication health and logs issues.
    """
    
    def __init__(self, executor: AsyncToolExecutor, check_interval: float = 30.0):
        self.executor = executor
        self.check_interval = check_interval
        self.health_checker = HealthChecker(executor)
        self.health_history: List[HealthSnapshot] = []
        self.is_monitoring = False
        
    def start_monitoring(self):
        """Start the monitoring loop."""
        self.is_monitoring = True
        log.info(f"Starting MCP communication monitoring (interval: {self.check_interval}s)")
        
        asyncio.create_task(self._monitoring_loop())
        
    def stop_monitoring(self):
        """Stop the monitoring loop."""
        self.is_monitoring = False
        log.info("Stopping MCP communication monitoring")
        
    async def _monitoring_loop(self):
        """Main monitoring loop."""
        while self.is_monitoring:
            try:
                # Perform health check
                health_results = self.health_checker.comprehensive_health_check()
                
                # Extract key metrics
                ping_check = health_results.get("checks", {}).get("ping", {})
                
                snapshot = HealthSnapshot(
                    timestamp=time.time(),
                    datetime_str=datetime.now().isoformat(),
                    ping_success=ping_check.get("success", False),
                    ping_duration_ms=ping_check.get("duration_ms", 0),
                    executor_stats=health_results.get("checks", {}).get("basic_status", {}),
                    overall_status=health_results.get("overall_status", "unknown"),
                    error=health_results.get("error")
                )
                
                # Add to history
                self.health_history.append(snapshot)
                
                # Keep only last 100 snapshots
                if len(self.health_history) > 100:
                    self.health_history = self.health_history[-100:]
                
                # Log health status
                if snapshot.overall_status == "healthy":
                    log.info(f"Health check OK - ping: {snapshot.ping_duration_ms:.1f}ms")
                else:
                    log.warning(f"Health check FAILED - status: {snapshot.overall_status}, ping: {snapshot.ping_success}")
                    
                # Check for communication issues
                self._analyze_health_trends()
                
                await asyncio.sleep(self.check_interval)
                
            except Exception as e:
                log.error(f"Error in monitoring loop: {e}")
                await asyncio.sleep(self.check_interval)
                
    def _analyze_health_trends(self):
        """Analyze recent health trends for patterns."""
        if len(self.health_history) < 3:
            return
            
        recent_snapshots = self.health_history[-3:]
        
        # Check for consecutive failures
        consecutive_failures = all(not s.ping_success for s in recent_snapshots)
        if consecutive_failures:
            log.error("ALERT: 3 consecutive ping failures detected - possible communication breakdown")
            
        # Check for slow response times
        avg_ping_time = sum(s.ping_duration_ms for s in recent_snapshots) / len(recent_snapshots)
        if avg_ping_time > 1000:  # 1 second
            log.warning(f"ALERT: Average ping time is high: {avg_ping_time:.1f}ms")
            
        # Check for status changes
        if len(self.health_history) >= 2:
            prev_status = self.health_history[-2].overall_status
            curr_status = self.health_history[-1].overall_status
            
            if prev_status != curr_status:
                log.info(f"Health status changed: {prev_status} -> {curr_status}")
                
    def get_health_summary(self) -> Dict:
        """Get a summary of recent health data."""
        if not self.health_history:
            return {"status": "no_data", "message": "No health data available"}
            
        recent_snapshots = self.health_history[-10:]  # Last 10 snapshots
        
        successful_pings = sum(1 for s in recent_snapshots if s.ping_success)
        avg_ping_time = sum(s.ping_duration_ms for s in recent_snapshots) / len(recent_snapshots)
        
        return {
            "status": "summary",
            "total_snapshots": len(self.health_history),
            "recent_snapshots": len(recent_snapshots),
            "ping_success_rate": successful_pings / len(recent_snapshots),
            "avg_ping_time_ms": round(avg_ping_time, 2),
            "latest_status": recent_snapshots[-1].overall_status,
            "latest_timestamp": recent_snapshots[-1].datetime_str
        }
        
    def export_health_data(self, filename: str = "health_data.json"):
        """Export health data to JSON file."""
        data = {
            "export_timestamp": datetime.now().isoformat(),
            "total_snapshots": len(self.health_history),
            "snapshots": [asdict(snapshot) for snapshot in self.health_history]
        }
        
        with open(filename, 'w') as f:
            json.dump(data, f, indent=2)
            
        log.info(f"Health data exported to {filename}")


def main():
    """Main function to run the communication monitor."""
    log.info("Starting MCP Communication Monitor")
    
    # Create and start the executor
    executor = AsyncToolExecutor()
    executor.start()
    
    try:
        # Create the monitor
        monitor = CommunicationMonitor(executor, check_interval=10.0)  # Check every 10 seconds
        
        # Start monitoring
        monitor.start_monitoring()
        
        # Run for a specified duration or until interrupted
        try:
            # Keep the main thread alive
            while True:
                time.sleep(1)
                
                # Print summary every 60 seconds
                if int(time.time()) % 60 == 0:
                    summary = monitor.get_health_summary()
                    log.info(f"Health summary: {summary}")
                    
        except KeyboardInterrupt:
            log.info("Monitoring interrupted by user")
            
    except Exception as e:
        log.error(f"Monitor failed: {e}")
        raise
    finally:
        # Clean up
        monitor.stop_monitoring()
        monitor.export_health_data()
        executor.stop()
        log.info("MCP Communication Monitor stopped")


if __name__ == "__main__":
    main()
