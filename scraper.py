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
    FIXED: Handle JavaScript rendering dan ambil data dari window object.
    """
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/108.0.0.0 Safari/537.36",
            viewport={'width': 1920, 'height': 1080},
            # Tambah timeout lebih lama
            timeout=120000
        )
        
        # Enable JavaScript dan biarkan load
        page = await context.new_page()
        
        try:
            base_url = "https://kickass-anime.ru"
            print("🚀 Membuka halaman anime...")
            
            # Pergi ke URL dengan wait until network idle
            await page.goto(f"{base_url}/anime", wait_until="networkidle", timeout=120000)
            
            # Tunggu sampai data JavaScript loaded
            print("⏳ Menunggu data JavaScript load...")
            
            # Cara 1: Tunggu sampai element anime muncul
            try:
                await page.wait_for_selector(".show-item", timeout=30000)
                print("✅ Element anime ditemukan")
            except:
                print("⚠️  Element anime tidak ditemukan, lanjut dengan cara lain")
            
            # Cara 2: Extract data langsung dari JavaScript window object
            print("🔍 Mencoba extract data dari JavaScript...")
            
            anime_data = await extract_data_from_javascript(page, base_url)
            
            if anime_data:
                print(f"🎉 Berhasil extract {len(anime_data)} anime dari JavaScript")
                await save_anime_data(anime_data)
                return anime_data
            
            # Fallback: Scrape manual kalau JavaScript method gagal
            print("🔄 Fallback ke metode scraping manual...")
            return await scrape_manually(page, context, base_url)

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
        # Execute JavaScript untuk ambil data dari window.KAA
        js_code = """
        () => {
            if (window.KAA && window.KAA.data && window.KAA.data[0] && window.KAA.data[0].shows) {
                return window.KAA.data[0].shows.map(show => ({
                    slug: show.slug,
                    title: show.title,
                    title_en: show.title_en || '',
                    year: show.year,
                    type: show.type,
                    status: show.status,
                    synopsis: show.synopsis || '',
                    genres: show.genres || [],
                    locales: show.locales || [],
                    episode_duration: show.episode_duration || 0,
                    poster: show.poster || {},
                    watch_uri: show.watch_uri || ''
                }));
            }
            return null;
        }
        """
        
        raw_data = await page.evaluate(js_code)
        
        if not raw_data:
            print("❌ Data tidak ditemukan di window.KAA")
            return None
        
        processed_data = []
        for item in raw_data:
            # Build URLs
            detail_url = f"{base_url}/{item['slug']}"
            watch_url = f"{base_url}{item['watch_uri']}" if item['watch_uri'] else None
            
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
                "sinopsis": item['synopsis'],
                "genre": item['genres'],
                "bahasa": item['locales'],
                "durasi_episode": item['episode_duration'],
                "url_poster": poster_url,
                "url_detail": detail_url,
                "url_watch": watch_url,
                "slug": item['slug'],
                "last_updated": datetime.now().isoformat()
            }
            processed_data.append(anime_info)
        
        return processed_data
        
    except Exception as e:
        print(f"❌ Gagal extract data JavaScript: {e}")
        return None

async def scrape_manually(page, context, base_url):
    """
    Fallback method: Scrape manual dari HTML.
    """
    print("🔄 Memulai scraping manual...")
    
    try:
        # Coba filter by year untuk dapat data spesifik
        years = await get_available_years(page)
        if not years:
            years = [2024, 2023, 2022]  # Default years
        
        all_data = []
        
        for year in years[:2]:  # Batasi 2 tahun untuk testing
            print(f"📅 Memproses tahun {year}...")
            
            # Filter by year
            await filter_by_year(page, year)
            await asyncio.sleep(3)
            
            # Scrape anime list
            year_data = await scrape_anime_list(page, context, base_url, year)
            all_data.extend(year_data)
        
        return all_data
        
    except Exception as e:
        print(f"❌ Gagal scraping manual: {e}")
        return []

async def get_available_years(page):
    """Dapatkan tahun yang tersedia dari filter."""
    try:
        # Klik tombol Year
        year_btn = await page.query_selector("button:has-text('Year')")
        if year_btn:
            await year_btn.click()
            await asyncio.sleep(2)
            
            # Ambil semua tahun dari dialog
            year_buttons = await page.query_selector_all(".v-chip--clickable .v-chip__content")
            years = []
            
            for btn in year_buttons:
                text = await btn.inner_text()
                if text.isdigit() and 1900 <= int(text) <= 2030:
                    years.append(int(text))
            
            # Tutup dialog
            close_btn = await page.query_selector("button:has-text('Close')")
            if close_btn:
                await close_btn.click()
            
            return sorted(years, reverse=True)
    
    except Exception as e:
        print(f"❌ Gagal dapatkan tahun: {e}")
    
    return None

async def filter_by_year(page, year):
    """Filter anime by year."""
    try:
        # Buka dialog Year
        year_btn = await page.query_selector("button:has-text('Year')")
        if year_btn:
            await year_btn.click()
            await asyncio.sleep(2)
            
            # Pilih tahun
            year_option = await page.query_selector(f".v-chip__content:has-text('{year}')")
            if year_option:
                await year_option.click()
                await asyncio.sleep(2)
            
            # Tutup dialog
            close_btn = await page.query_selector("button:has-text('Close')")
            if close_btn:
                await close_btn.click()
            
            await asyncio.sleep(3)  # Tunggu data reload
            return True
    
    except Exception as e:
        print(f"❌ Gagal filter by year {year}: {e}")
    
    return False

async def scrape_anime_list(page, context, base_url, year):
    """Scrape anime dari list view."""
    scraped_data = []
    
    try:
        # Tunggu anime items
        await page.wait_for_selector(".show-item", timeout=15000)
        anime_items = await page.query_selector_all(".show-item")
        
        print(f"📊 Menemukan {len(anime_items)} anime untuk tahun {year}")
        
        for i, item in enumerate(anime_items[:5]):  # Batasi 5 untuk testing
            try:
                print(f"🎬 Processing anime {i+1}/{len(anime_items)}")
                
                # Get basic info dari card
                title_elem = await item.query_selector(".show-title span")
                title = await title_elem.inner_text() if title_elem else "Unknown"
                
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
                
                # Get genres
                genre_elems = await item.query_selector_all(".v-chip--outlined .v-chip__content")
                genres = []
                for genre_elem in genre_elems:
                    genre_text = await genre_elem.inner_text()
                    if not genre_text.isdigit():  # Exclude years
                        genres.append(genre_text)
                
                anime_info = {
                    "judul": title,
                    "tahun": year,
                    "genre": genres,
                    "url_poster": poster_url,
                    "url_detail": detail_url,
                    "url_watch": None,
                    "sinopsis": "Akan di-scrape dari detail page",
                    "last_updated": datetime.now().isoformat()
                }
                
                scraped_data.append(anime_info)
                print(f"✅ {title}")
                
            except Exception as e:
                print(f"❌ Gagal process anime {i+1}: {e}")
                continue
                
    except Exception as e:
        print(f"❌ Gagal scrape list: {e}")
    
    return scraped_data

async def save_anime_data(data):
    """Save anime data to JSON file."""
    filename = 'anime_data_kickass.json'
    
    try:
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        
        print(f"💾 Data disimpan ke {filename}")
        print(f"📊 Total {len(data)} anime")
        
    except Exception as e:
        print(f"❌ Gagal save data: {e}")

async def main():
    """Main function."""
    print("🚀 KICKASS ANIME SCRAPER - JAVASCRIPT FIXED")
    print("=" * 50)
    print("Metode: Extract data dari JavaScript window object")
    print("Fallback: Manual scraping jika JavaScript gagal")
    print("=" * 50)
    
    data = await scrape_kickass_anime_all_years()
    
    if data:
        print(f"\n🎉 SCRAPING SELESAI!")
        print(f"📊 Total anime: {len(data)}")
        print(f"📅 Tahun: {list(set([d['tahun'] for d in data if d.get('tahun')]))}")
    else:
        print("\n❌ SCRAPING GAGAL!")

if __name__ == "__main__":
    asyncio.run(main())
