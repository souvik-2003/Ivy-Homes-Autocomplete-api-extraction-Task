import requests
from time import sleep
import logging
from random import uniform
from string import ascii_lowercase
from collections import defaultdict


class NameHarvester:
    def __init__(self, target_endpoint, api_list, pause_duration=2, retry_limit=3, recursion_limit=2):

        self._setup_logging()
        

        self.endpoint = target_endpoint
        self.supported_apis = api_list
        self.pause = pause_duration
        self.max_attempts = retry_limit
        self.depth_limit = recursion_limit
        

        self.discovered_entries = {api: set() for api in self.supported_apis}
        self.api_query_metrics = {api: 0 for api in self.supported_apis}
    
    def _setup_logging(self):
        """Configure the logging system"""
        log_format = '%(asctime)s - %(levelname)s - %(message)s'
        logging.basicConfig(level=logging.INFO, format=log_format)
    
    def _perform_query(self, api_version, search_term):
        """Execute API request with retry logic"""
        endpoint_url = f"{self.endpoint}/{api_version}/autocomplete"
        attempt = 0
        
        while attempt <= self.max_attempts:
            try:
                jitter = uniform(0.5, 1.5)
                
                self.api_query_metrics[api_version] += 1
                
                response = requests.get(endpoint_url, params={"query": search_term})
                response.raise_for_status()
                return response.json()
                
            except requests.exceptions.HTTPError as error:
                if error.response.status_code == 429:  # Rate limiting
                    backoff_time = self.pause * (attempt + 1) * jitter
                    logging.warning(f"Rate limited on {api_version}. Waiting {backoff_time:.2f}s")
                    sleep(backoff_time)
                    attempt += 1
                    print("Number of searches made for v1:", harvester.api_query_metrics["v1"])
                    print("Number of searches made for v2:", harvester.api_query_metrics["v2"])
                else:
                    logging.error(f"HTTP error: {error}")
                    return None
            except Exception as error:
                logging.error(f"Request failed: {error}")
                return None
        
        logging.error(f"Maximum retries exceeded for {search_term} on {api_version}")
        return None
    
    def crawl(self, api_version, prefix="", current_level=0):
        """Recursively harvest names from the API"""
        if current_level > self.depth_limit:
            return
            
        result_data = self._perform_query(api_version, prefix)
        if not result_data:
            return
            
        for entry in result_data.get("results", []):
            if entry not in self.discovered_entries[api_version]:
                self.discovered_entries[api_version].add(entry)
                logging.info(f"Found in {api_version}: {entry}")
                
                self.crawl(
                    api_version, 
                    prefix=entry, 
                    current_level=current_level+1
                )
        
        variation = uniform(0.8, 1.2)
        sleep(self.pause * variation)
    
    def start_harvesting(self):
        """Main execution method"""
        logging.info("Beginning data collection process...")
        
        for version in self.supported_apis:
            logging.info(f"Processing API version: {version}")
            
            for character in ascii_lowercase:
                self.crawl(version, prefix=character)
            
            entry_count = len(self.discovered_entries[version])
            query_count = self.api_query_metrics[version]
            logging.info(f"API {version} results: {entry_count} entries found in {query_count} queries")
        
        total_entries = sum(len(entries) for entries in self.discovered_entries.values())
        total_queries = sum(self.api_query_metrics.values())
        logging.info(f"Collection complete: {total_entries} total entries from {total_queries} queries")
        
        self._save_results()
        
    def _save_results(self):
        """Write collected data to output file"""
        with open("harvested_entries.txt", "w") as output_file:
            for version in self.supported_apis:
                output_file.write(f"--- {version} ---\n")
                for entry in sorted(self.discovered_entries[version]):
                    output_file.write(f"{entry}\n")
        logging.info("Results saved to harvested_entries.txt")


if __name__ == "__main__":
    SERVER_ADDRESS = "http://35.200.185.69:8000/"
    AVAILABLE_VERSIONS = ["v1", "v2", "v3"]
    
    
    harvester = NameHarvester(
        target_endpoint=SERVER_ADDRESS,
        api_list=AVAILABLE_VERSIONS
    )
    harvester.start_harvesting()
