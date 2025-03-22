#!/usr/bin/env python3
"""
API Name Explorer - A sophisticated tool for discovering and extracting entity names 
from multiple API versions with intelligent crawling capabilities.
"""

import asyncio
import aiohttp
import logging
import argparse
import json
import time
import sys
from pathlib import Path
from typing import Dict, Set, List, Optional, Union
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor


class APIExplorer:
    """Advanced API exploration system that intelligently discovers names across multiple API versions."""
    
    def __init__(self, config: Dict):
        """Initialize the explorer with configuration settings."""
        # Core settings
        self.server_url = config.get('server_url')
        self.api_versions = config.get('api_versions', [])
        self.search_characters = config.get('search_characters', 'abcdefghijklmnopqrstuvwxyz')
        
        # Performance settings
        self.concurrency_limit = config.get('concurrency_limit', 5)
        self.request_pause = config.get('request_pause', 1.5)
        self.retry_attempts = config.get('retry_attempts', 3)
        self.backoff_multiplier = config.get('backoff_multiplier', 2)
        self.max_exploration_depth = config.get('max_exploration_depth', 2)
        
        # Output settings
        self.result_filename = config.get('result_filename', f"api_discoveries_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt")
        self.json_output = config.get('json_output', False)
        
        # Initialize data structures
        self.discoveries: Dict[str, Set[str]] = {version: set() for version in self.api_versions}
        self.request_metrics: Dict[str, int] = {version: 0 for version in self.api_versions}
        self.exploration_queue: List[Dict] = []
        
        # Configure logging
        self._setup_logging(config.get('verbose', False))
        
        self.logger.info(f"Explorer initialized with {len(self.api_versions)} API versions")
    
    def _setup_logging(self, verbose: bool) -> None:
        """Configure the logging system with appropriate verbosity."""
        self.logger = logging.getLogger("APIExplorer")
        handler = logging.StreamHandler()
        
        formatter = logging.Formatter(
            '%(asctime)s [%(levelname)s] %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        handler.setFormatter(formatter)
        
        self.logger.addHandler(handler)
        self.logger.setLevel(logging.DEBUG if verbose else logging.INFO)
        
        # Create file handler for persistent logging
        file_handler = logging.FileHandler(f"explorer_{datetime.now().strftime('%Y%m%d')}.log")
        file_handler.setFormatter(formatter)
        self.logger.addHandler(file_handler)
    
    async def run(self) -> None:
        """Execute the full exploration process across all API versions."""
        self.logger.info("Starting API exploration...")
        
        start_time = time.time()
        
        # Initialize the exploration queue with seed queries
        for version in self.api_versions:
            for char in self.search_characters:
                self.exploration_queue.append({
                    'version': version,
                    'query': char,
                    'depth': 0
                })
        
        # Process the queue with controlled concurrency
        async with aiohttp.ClientSession() as session:
            tasks = []
            semaphore = asyncio.Semaphore(self.concurrency_limit)
            
            while self.exploration_queue:
                item = self.exploration_queue.pop(0)
                
                # Create a task for each queue item
                task = asyncio.create_task(
                    self._process_queue_item(session, semaphore, item)
                )
                tasks.append(task)
            
            # Wait for all tasks to complete
            if tasks:
                await asyncio.gather(*tasks)
        
        # Calculate execution statistics
        total_time = time.time() - start_time
        total_discoveries = sum(len(names) for names in self.discoveries.values())
        total_requests = sum(self.request_metrics.values())
        
        # Log the results
        self.logger.info(f"Exploration completed in {total_time:.2f} seconds")
        self.logger.info(f"Total discoveries: {total_discoveries} names")
        self.logger.info(f"Total API requests: {total_requests}")
        
        for version in self.api_versions:
            self.logger.info(f"API {version}: {len(self.discoveries[version])} names from {self.request_metrics[version]} requests")
        
        # Save the results
        self._save_results()
    
    async def _process_queue_item(self, session: aiohttp.ClientSession, 
                                 semaphore: asyncio.Semaphore, 
                                 item: Dict) -> None:
        """Process a single exploration queue item with rate limiting."""
        version = item['version']
        query = item['query']
        depth = item['depth']
        
        # Skip if we've reached maximum depth
        if depth > self.max_exploration_depth:
            return
        
        # Use semaphore to limit concurrent requests
        async with semaphore:
            results = await self._execute_api_request(session, version, query)
            
            # Process results if available
            if results:
                for name in results:
                    if name not in self.discoveries[version]:
                        # Record new discovery
                        self.discoveries[version].add(name)
                        self.logger.debug(f"Discovered '{name}' from {version}")
                        
                        # Add to exploration queue for deeper discovery
                        self.exploration_queue.append({
                            'version': version,
                            'query': name,
                            'depth': depth + 1
                        })
            
            # Respect rate limits
            await asyncio.sleep(self.request_pause)
    
    async def _execute_api_request(self, session: aiohttp.ClientSession, 
                                  version: str, query: str) -> Optional[List[str]]:
        """Execute an API request with retry logic."""
        url = f"{self.server_url}/{version}/autocomplete"
        params = {"query": query}
        
        # Track request metrics
        self.request_metrics[version] += 1
        
        # Implement retry logic
        for attempt in range(self.retry_attempts):
            try:
                async with session.get(url, params=params) as response:
                    if response.status == 200:
                        data = await response.json()
                        return data.get("results", [])
                    
                    elif response.status == 429:  # Rate limiting
                        wait_time = self.request_pause * (self.backoff_multiplier ** attempt)
                        self.logger.warning(f"Rate limited on {version}. Waiting {wait_time:.2f}s (attempt {attempt+1}/{self.retry_attempts})")
                        await asyncio.sleep(wait_time)
                    
                    else:
                        self.logger.error(f"HTTP error {response.status} for {query} on {version}")
                        return None
                        
            except aiohttp.ClientError as e:
                self.logger.error(f"Request error: {e}")
                
                # Only retry on connection errors
                if isinstance(e, (aiohttp.ClientConnectionError, aiohttp.ServerTimeoutError)):
                    wait_time = self.request_pause * (self.backoff_multiplier ** attempt)
                    self.logger.warning(f"Connection error, retrying in {wait_time:.2f}s")
                    await asyncio.sleep(wait_time)
                else:
                    return None
        
        self.logger.error(f"All retry attempts failed for {query} on {version}")
        return None
    
    def _save_results(self) -> None:
        """Save the exploration results to the specified output file."""
        path = Path(self.result_filename)
        
        # Create directory if it doesn't exist
        path.parent.mkdir(parents=True, exist_ok=True)
        
        # Save in JSON format if requested
        if self.json_output:
            json_filename = path.with_suffix('.json')
            # Convert sets to lists for JSON serialization
            json_data = {
                'metadata': {
                    'timestamp': datetime.now().isoformat(),
                    'api_versions': self.api_versions,
                    'total_requests': sum(self.request_metrics.values()),
                    'request_metrics': self.request_metrics
                },
                'discoveries': {version: sorted(list(names)) for version, names in self.discoveries.items()}
            }
            
            with open(json_filename, 'w') as f:
                json.dump(json_data, f, indent=2)
            
            self.logger.info(f"Results saved to {json_filename}")
        
        # Save in text format
        with open(path, 'w') as f:
            f.write(f"API Name Explorer Results - {datetime.now()}\n")
            f.write(f"{'='*60}\n\n")
            
            # Summary statistics
            f.write("Summary:\n")
            total_discoveries = sum(len(names) for names in self.discoveries.values())
            f.write(f"  Total unique names discovered: {total_discoveries}\n")
            f.write(f"  Total API requests: {sum(self.request_metrics.values())}\n\n")
            
            # Version details
            for version in self.api_versions:
                f.write(f"\n{'='*20} {version} {'='*20}\n")
                f.write(f"  Discovered {len(self.discoveries[version])} names with {self.request_metrics[version]} requests\n\n")
                
                for name in sorted(self.discoveries[version]):
                    f.write(f"  {name}\n")
        
        self.logger.info(f"Results saved to {path}")


def parse_arguments():
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="API Name Explorer - Discover entity names from multiple API versions"
    )
    
    parser.add_argument(
        "--server", 
        default="http://35.200.185.69:8000",
        help="API server URL (default: http://35.200.185.69:8000)"
    )
    
    parser.add_argument(
        "--versions", 
        default="v1,v2,v3",
        help="Comma-separated API versions to explore (default: v1,v2,v3)"
    )
    
    parser.add_argument(
        "--concurrency", 
        type=int, 
        default=5,
        help="Maximum concurrent requests (default: 5)"
    )
    
    parser.add_argument(
        "--pause", 
        type=float, 
        default=1.5,
        help="Pause between requests in seconds (default: 1.5)"
    )
    
    parser.add_argument(
        "--retries", 
        type=int, 
        default=3,
        help="Maximum retry attempts for failed requests (default: 3)"
    )
    
    parser.add_argument(
        "--depth", 
        type=int, 
        default=2,
        help="Maximum exploration depth (default: 2)"
    )
    
    parser.add_argument(
        "--output", 
        default="api_discoveries.txt",
        help="Output filename (default: api_discoveries.txt)"
    )
    
    parser.add_argument(
        "--json", 
        action="store_true",
        help="Also save results in JSON format"
    )
    
    parser.add_argument(
        "--verbose", 
        action="store_true",
        help="Enable verbose logging"
    )
    
    return parser.parse_args()


async def main():
    """Main entry point for the application."""
    # Parse command-line arguments
    args = parse_arguments()
    
    # Create configuration dictionary
    config = {
        'server_url': args.server,
        'api_versions': args.versions.split(','),
        'concurrency_limit': args.concurrency,
        'request_pause': args.pause,
        'retry_attempts': args.retries,
        'max_exploration_depth': args.depth,
        'result_filename': args.output,
        'json_output': args.json,
        'verbose': args.verbose
    }
    
    # Create and run the explorer
    explorer = APIExplorer(config)
    await explorer.run()


if __name__ == "__main__":
    # Configure asyncio event loop
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    
    # Run the main application
    asyncio.run(main())
