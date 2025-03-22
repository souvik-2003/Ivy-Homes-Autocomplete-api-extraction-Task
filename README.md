# Ivy_homes_assignment



## **Overview**
This script extracts names from an API endpoint using different API versions (`v1`, `v2`, `v3`). It performs recursive requests, handles rate limits, and stores unique names from each version.

## **Features**
- Queries the API with an autocomplete function.
- Handles rate limits with exponential backoff.
- Recursively extracts names to a specified depth.
- Logs the extraction process for easy debugging.
- Saves the extracted names to a text file (`harvested_entries.txt`).

## **Requirements**
Ensure you have Python installed along with the required library:

```sh
pip install requests
```

## **How It Works**
1. The script makes GET requests to the API at:
   ```
   http://35.200.185.69:8000/{api_version}/autocomplete?query={prefix}
   ```
2. It starts by querying each version (`v1`, `v2`, `v3`) with single letters (`a-z`).
3. Extracted names are stored and used to query further, following a depth limit.
4. Requests are retried in case of rate limiting (HTTP 429) or failures.
5. The extracted names are saved to `harvested_entries.txt`.

## **How to Run**
Run the script using:

```sh
python script.py
```

## **Output**
- Logs the extraction process.
- Saves extracted names in `harvested_entries.txt`.

## **Customization**
- Modify `MAX_RETRIES`, `DELAY`, and `max_depth` as needed.
- Change `BASE_URL` if the API endpoint changes.
