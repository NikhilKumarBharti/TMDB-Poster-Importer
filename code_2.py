import os
import re
import requests
from pathlib import Path
from dotenv import load_dotenv
from concurrent.futures import ThreadPoolExecutor, as_completed
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# Load environment variables from .env file
load_dotenv()

# Configuration
TMDB_API_KEY = os.getenv("TMDB_API_KEY")
TORRENT_FOLDER = os.getenv("TORRENT_FOLDER")
TMDB_API_BASE = "https://api.themoviedb.org/3"
TMDB_IMAGE_BASE = "https://image.tmdb.org/t/p/w500"
MAX_WORKERS = 10  # Number of concurrent threads

# Create a session with connection pooling and retries
session = requests.Session()
retry_strategy = Retry(
    total=3,
    backoff_factor=0.5,
    status_forcelist=[429, 500, 502, 503, 504]
)
adapter = HTTPAdapter(max_retries=retry_strategy, pool_connections=20, pool_maxsize=20)
session.mount("http://", adapter)
session.mount("https://", adapter)

def extract_movie_info(filename):
    """Extract movie title and year from torrent filename"""
    # Remove .torrent extension
    name = filename.replace('.torrent', '')
    
    # Try to match pattern: Title (Year) or Title Year
    match = re.search(r'^(.+?)\s*[\(\[]?(\d{4})[\)\]]?', name)
    
    if match:
        title = match.group(1).strip()
        year = match.group(2)
        # Clean up title - remove quality indicators, tags, etc.
        title = re.sub(r'\[.*?\]|\(.*?\)|1080p|720p|BluRay|WEBRip|YTS\.MX|YTS|S\.\d+', '', title)
        title = title.strip()
        return title, year
    
    return None, None

def search_movie(title, year):
    """Search for movie on TMDB"""
    url = f"{TMDB_API_BASE}/search/movie"
    params = {
        "api_key": TMDB_API_KEY,
        "query": title,
        "year": year
    }
    
    try:
        response = session.get(url, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        if data['results']:
            return data['results'][0]
        return None
    except Exception as e:
        print(f"  ✗ Error searching for {title} ({year}): {e}")
        return None

def download_poster(poster_path, save_path):
    """Download poster image from TMDB"""
    if not poster_path:
        return False
    
    url = f"{TMDB_IMAGE_BASE}{poster_path}"
    
    try:
        response = session.get(url, timeout=10)
        response.raise_for_status()
        
        with open(save_path, 'wb') as f:
            f.write(response.content)
        return True
    except Exception as e:
        print(f"  ✗ Error downloading poster: {e}")
        return False

def process_single_torrent(torrent_file, folder):
    """Process a single torrent file"""
    filename = torrent_file.name
    result = {
        'filename': filename,
        'success': False,
        'message': ''
    }
    
    # Extract movie info
    title, year = extract_movie_info(filename)
    
    if not title or not year:
        result['message'] = "Could not parse movie info"
        return result
    
    # Check if poster already exists
    poster_filename = torrent_file.stem + ".jpg"
    poster_path = folder / poster_filename
    
    if poster_path.exists():
        result['success'] = True
        result['message'] = f"Poster already exists: {poster_filename}"
        return result
    
    # Search for movie
    movie = search_movie(title, year)
    
    if not movie:
        result['message'] = f"Movie not found: {title} ({year})"
        return result
    
    # Download poster
    success = download_poster(movie.get('poster_path'), poster_path)
    
    if success:
        result['success'] = True
        result['message'] = f"✓ Downloaded: {poster_filename}"
    else:
        result['message'] = f"Failed to download poster for: {title}"
    
    return result

def process_torrents(folder_path):
    """Process all torrent files in folder with parallel downloads"""
    folder = Path(folder_path)
    
    if not folder.exists():
        print(f"Folder not found: {folder_path}")
        return
    
    torrent_files = list(folder.glob("*.torrent"))
    
    if not torrent_files:
        print("No .torrent files found in folder")
        return
    
    print(f"Found {len(torrent_files)} torrent files")
    print(f"Processing with {MAX_WORKERS} concurrent threads...\n")
    
    success_count = 0
    skip_count = 0
    fail_count = 0
    
    # Process torrents in parallel
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        # Submit all tasks
        future_to_file = {
            executor.submit(process_single_torrent, tf, folder): tf 
            for tf in torrent_files
        }
        
        # Process completed tasks as they finish
        for future in as_completed(future_to_file):
            result = future.result()
            
            if result['success']:
                if "already exists" in result['message']:
                    skip_count += 1
                    print(f"⊙ {result['filename']}: Already exists")
                else:
                    success_count += 1
                    print(f"✓ {result['filename']}: Downloaded")
            else:
                fail_count += 1
                print(f"✗ {result['filename']}: {result['message']}")
    
    # Print summary
    print("\n" + "=" * 50)
    print(f"Summary:")
    print(f"  Downloaded: {success_count}")
    print(f"  Skipped (already exists): {skip_count}")
    print(f"  Failed: {fail_count}")
    print(f"  Total: {len(torrent_files)}")

def main():
    # Check if API key is set
    if not TMDB_API_KEY:
        print("ERROR: TMDB_API_KEY not found in .env file!")
        print("Please create a .env file with: TMDB_API_KEY=your_api_key_here")
        print("Get a free API key at: https://www.themoviedb.org/settings/api")
        return
    
    # Check if folder path is set
    if not TORRENT_FOLDER or TORRENT_FOLDER == "/path/to/your/torrents":
        print("ERROR: TORRENT_FOLDER not found in .env file!")
        print("Please add to .env file: TORRENT_FOLDER=/path/to/your/torrents")
        return
    
    print("Movie Poster Fetcher (Parallel Mode)")
    print("=" * 50)
    process_torrents(TORRENT_FOLDER)
    print("=" * 50)
    print("Done!")

if __name__ == "__main__":
    main()