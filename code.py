import os
import re
import requests
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Configuration
TMDB_API_KEY = os.getenv("TMDB_API_KEY")
TORRENT_FOLDER = os.getenv("TORRENT_FOLDER")
TMDB_API_BASE = "https://api.themoviedb.org/3"
TMDB_IMAGE_BASE = "https://image.tmdb.org/t/p/w500"

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
        response = requests.get(url, params=params)
        response.raise_for_status()
        data = response.json()
        
        if data['results']:
            return data['results'][0]  # Return first result
        return None
    except Exception as e:
        print(f"Error searching for {title} ({year}): {e}")
        return None

def download_poster(poster_path, save_path):
    """Download poster image from TMDB"""
    if not poster_path:
        return False
    
    url = f"{TMDB_IMAGE_BASE}{poster_path}"
    
    try:
        response = requests.get(url)
        response.raise_for_status()
        
        with open(save_path, 'wb') as f:
            f.write(response.content)
        return True
    except Exception as e:
        print(f"Error downloading poster: {e}")
        return False

def process_torrents(folder_path):
    """Process all torrent files in folder and download posters"""
    folder = Path(folder_path)
    
    if not folder.exists():
        print(f"Folder not found: {folder_path}")
        return
    
    torrent_files = list(folder.glob("*.torrent"))
    
    if not torrent_files:
        print("No .torrent files found in folder")
        return
    
    print(f"Found {len(torrent_files)} torrent files\n")
    
    for torrent_file in torrent_files:
        filename = torrent_file.name
        print(f"Processing: {filename}")
        
        # Extract movie info
        title, year = extract_movie_info(filename)
        
        if not title or not year:
            print(f"  ✗ Could not parse movie info from filename\n")
            continue
        
        print(f"  Detected: {title} ({year})")
        
        # Search for movie
        movie = search_movie(title, year)
        
        if not movie:
            print(f"  ✗ Movie not found on TMDB\n")
            continue
        
        print(f"  ✓ Found: {movie['title']} ({movie.get('release_date', '')[:4]})")
        
        # Download poster
        poster_filename = torrent_file.stem + ".jpg"
        poster_path = folder / poster_filename
        
        if poster_path.exists():
            print(f"  ⊙ Poster already exists: {poster_filename}\n")
            continue
        
        success = download_poster(movie.get('poster_path'), poster_path)
        
        if success:
            print(f"  ✓ Poster saved: {poster_filename}\n")
        else:
            print(f"  ✗ Failed to download poster\n")

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
    
    print("Movie Poster Fetcher")
    print("=" * 50)
    process_torrents(TORRENT_FOLDER)
    print("=" * 50)
    print("Done!")

if __name__ == "__main__":
    main()