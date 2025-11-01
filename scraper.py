import asyncio
from playwright.async_api import async_playwright
import json
from urllib.parse import urljoin
import re
import os
from datetime import datetime

async def scrape_kickass_anime_all_years():
    """
    Scrape data anime dari kickass-anime.ru untuk SEMUA tahun.
    OPTIMIZED FOR GITHUB ACTIONS
    """
    async with async_playwright() as p:
        # Install browser dulu buat GitHub Actions
        browser = await p.chromium.launch(
            headless=True,
            args=['--no-sandbox', '--disable-dev-shm-usage']
        )
        
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/108.0.0.0 Safari/537.36",
            viewport={'width': 1920, 'height': 1080}
        )
        
        page = await context.new_page()
        
        try:
            base_url = "https://kickass-anime.ru"
            print("🚀 Membuka halaman anime...")
            
            # Pergi ke URL dengan timeout yang cukup
            await page.goto(f"{base_url}/anime", wait_until="domcontentloaded", timeout=60000)
            
            # Tunggu sampai data JavaScript loaded
            print("⏳ Menunggu data JavaScript load...")
            
            # Tunggu element utama
            try:
                await page.wait_for_selector(".show-item", timeout=30000)
                print("✅ Element anime ditemukan")
            except:
                print("⚠️  Element anime tidak ditemukan, coba cara lain...")
            
            # Extract data dari JavaScript - METHOD UTAMA
            print("🔍 Mencoba extract data dari JavaScript window.KAA...")
            
            anime_data = await extract_data_from_javascript(page, base_url)
            
            if anime_data:
                print(f"🎉 Berhasil extract {len(anime_data)} anime dari JavaScript")
                await save_anime_data(anime_data)
                return anime_data
            
            # Fallback ke manual scraping
            print("🔄 Fallback ke metode scraping manual...")
            manual_data = await scrape_manually_simple(page, base_url)
            
            if manual_data:
                await save_anime_data(manual_data)
                return manual_data
            
            return []
            
        except Exception as e:
            print(f"💥 ERROR: {e}")
            return []
        finally:
            await browser.close()

async def extract_data_from_javascript(page, base_url):
    """
    Extract data anime langsung dari JavaScript window object.
    Ini cara PALING EFEKTIF karena data sudah ada di JavaScript.
    """
    try:
        # Tunggu dulu sampai window.KAA tersedia
        await page.wait_for_function('window.KAA && window.KAA.data', timeout=15000)
        print("✅ window.KAA ditemukan")
        
        # Execute JavaScript untuk ambil data dari window.KAA
        js_code = """
        () => {
            try {
                if (window.KAA && window.KAA.data && window.KAA.data[0] && window.KAA.data[0].shows) {
                    const shows = window.KAA.data[0].shows;
                    console.log('Found', shows.length, 'shows in KAA');
                    
                    return shows.map(show => ({
                        slug: show.slug || '',
                        title: show.title || '',
                        title_en: show.title_en || '',
                        year: show.year || 0,
                        type: show.type || '',
                        status: show.status || '',
                        synopsis: show.synopsis || '',
                        genres: show.genres || [],
                        locales: show.locales || [],
                        episode_duration: show.episode_duration || 0,
                        poster: show.poster || {},
                        watch_uri: show.watch_uri || ''
                    }));
                }
                return null;
            } catch (e) {
                console.error('Error in KAA extraction:', e);
                return null;
            }
        }
        """
        
        raw_data = await page.evaluate(js_code)
        
        if not raw_data:
            print("❌ Data tidak ditemukan di window.KAA")
            return None
        
        print(f"📊 Mendapatkan {len(raw_data)} anime dari JavaScript")
        
        processed_data = []
        for item in raw_data[:20]:  # Batasi 20 anime untuk GitHub Actions
            try:
                # Build URLs
                detail_url = f"{base_url}/{item['slug']}" if item.get('slug') else ""
                
                # Build watch URL
                watch_url = None
                if item.get('watch_uri'):
                    watch_url = f"{base_url}{item['watch_uri']}"
                
                # Build poster URL
                poster_url = "Tidak tersedia"
                if item.get('poster') and item['poster'].get('hq'):
                    poster_filename = item['poster']['hq']
                    poster_url = f"https://kickass-anime.ru/image/poster/{poster_filename}"
                
                anime_info = {
                    "judul": item['title'],
                    "judul_english": item['title_en'],
                    "tahun": item['year'],
                    "tipe": item['type'],
                    "status": item['status'],
                    "sinopsis": item['synopsis'][:200] + "..." if item['synopsis'] and len(item['synopsis']) > 200 else item['synopsis'],
                    "genre": item['genres'],
                    "bahasa": item['locales'],
                    "durasi_episode": item['episode_duration'],
                    "url_poster": poster_url,
                    "url_detail": detail_url,
                    "url_watch": watch_url,
                    "slug": item['slug'],
                    "scraped_at": datetime.now().isoformat()
                }
                processed_data.append(anime_info)
                
            except Exception as e:
                print(f"❌ Gagal process item: {e}")
                continue
        
        return processed_data
        
    except Exception as e:
        print(f"❌ Gagal extract data JavaScript: {e}")
        return None

async def scrape_manually_simple(page, base_url):
    """
    Simple manual scraping fallback untuk GitHub Actions.
    """
    print("🔄 Memulai simple manual scraping...")
    
    try:
        # Tunggu anime items
        await page.wait_for_selector(".show-item", timeout=15000)
        anime_items = await page.query_selector_all(".show-item")
        
        print(f"📊 Menemukan {len(anime_items)} anime items")
        
        scraped_data = []
        
        for i, item in enumerate(anime_items[:10]):  # Batasi 10 untuk GitHub Actions
            try:
                # Get title
                title_elem = await item.query_selector(".show-title span")
                title = await title_elem.inner_text() if title_elem else f"Anime {i+1}"
                
                # Get poster
                poster_elem = await item.query_selector(".v-image__image--cover")
                poster_url = "Tidak tersedia"
                if poster_elem:
                    style = await poster_elem.get_attribute("style")
                    if style and 'url(' in style:
                        url_match = re.search(r'url\(["\']?([^"\'\)]+)["\']?\)', style)
                        if url_match:
                            poster_url = urljoin(base_url, url_match.group(1))
                
                # Get detail link
                detail_link = await item.query_selector("a.v-card--link")
                detail_url = ""
                if detail_link:
                    href = await detail_link.get_attribute("href")
                    detail_url = urljoin(base_url, href) if href else ""
                
                # Get year from badge
                year_badge = await item.query_selector(".poster-badge .v-chip__content")
                year = 2024
                if year_badge:
                    year_text = await year_badge.inner_text()
                    if year_text.isdigit():
                        year = int(year_text)
                
                # Get genres
                genre_elems = await item.query_selector_all(".v-chip--outlined .v-chip__content")
                genres = []
                for genre_elem in genre_elems:
                    genre_text = await genre_elem.inner_text()
                    if not genre_text.isdigit() and genre_text not in ['TV', 'SUB', 'DUB', 'MOVIE', 'SPECIAL', 'OVA']:
                        genres.append(genre_text)
                
                anime_info = {
                    "judul": title,
                    "tahun": year,
                    "genre": genres,
                    "url_poster": poster_url,
                    "url_detail": detail_url,
                    "url_watch": None,
                    "sinopsis": "Scraped from list view",
                    "scraped_at": datetime.now().isoformat()
                }
                
                scraped_data.append(anime_info)
                print(f"✅ {title} ({year})")
                
            except Exception as e:
                print(f"❌ Gagal process anime {i+1}: {e}")
                continue
                
        return scraped_data
        
    except Exception as e:
        print(f"❌ Gagal simple manual scraping: {e}")
        return []

async def save_anime_data(data):
    """Save anime data to JSON file."""
    filename = 'anime_data_kickass.json'
    
    try:
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        
        print(f"💾 Data disimpan ke {filename}")
        print(f"📊 Total {len(data)} anime")
        
        # Print summary
        years = list(set([d['tahun'] for d in data if d.get('tahun')]))
        print(f"📅 Tahun: {sorted(years)}")
        
        # Print sample data
        if data:
            print(f"\n📝 Sample data:")
            for i, anime in enumerate(data[:3]):
                print(f"  {i+1}. {anime['judul']} ({anime['tahun']}) - {anime['genre'][:2]}")
        
    except Exception as e:
        print(f"❌ Gagal save data: {e}")

async def main():
    """Main function - OPTIMIZED FOR GITHUB ACTIONS"""
    print("🚀 KICKASS ANIME SCRAPER - GITHUB ACTIONS OPTIMIZED")
    print("=" * 60)
    print("Strategi:")
    print("1. Extract langsung dari JavaScript window.KAA (FAST)")
    print("2. Fallback ke simple manual scraping")
    print("3. Batasi data untuk GitHub Actions")
    print("=" * 60)
    
    start_time = datetime.now()
    data = await scrape_kickass_anime_all_years()
    end_time = datetime.now()
    
    duration = (end_time - start_time).total_seconds()
    
    if data:
        print(f"\n🎉 SCRAPING SELESAI!")
        print(f"⏱️  Durasi: {duration:.2f} detik")
        print(f"📊 Total anime: {len(data)}")
        
        # Stats
        genres_count = {}
        for anime in data:
            for genre in anime.get('genre', []):
                genres_count[genre] = genres_count.get(genre, 0) + 1
        
        print(f"🏷️  Genre unik: {len(genres_count)}")
        print(f"📅 Rentang tahun: {min([d['tahun'] for d in data])}-{max([d['tahun'] for d in data])}")
        
    else:
        print("\n❌ SCRAPING GAGAL - Tidak ada data yang didapat")

if __name__ == "__main__":
    asyncio.run(main())
