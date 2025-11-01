import asyncio
from playwright.async_api import async_playwright
import json
from urllib.parse import urljoin
import re
import os
from datetime import datetime

async def scrape_kickass_anime_all_years():
    """
    Scrape data anime dari kickass-anime.ru dengan FILTER YEAR yang benar.
    """
    async with async_playwright() as p:
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
            
            await page.goto(f"{base_url}/anime", wait_until="domcontentloaded", timeout=60000)
            
            # Tunggu data JavaScript
            print("⏳ Menunggu data JavaScript load...")
            await page.wait_for_selector(".show-item", timeout=30000)
            
            # DAPATKAN TAHUN YANG SEDANG DIFILTER
            current_year = await get_current_filtered_year(page)
            print(f"📅 Tahun yang sedang difilter: {current_year}")
            
            # Extract data dengan FILTER YEAR
            print("🔍 Extract data dengan filter tahun...")
            anime_data = await extract_data_with_year_filter(page, base_url, current_year)
            
            if anime_data:
                print(f"🎉 Berhasil extract {len(anime_data)} anime untuk tahun {current_year}")
                await save_anime_data(anime_data, current_year)
                return anime_data
            
            return []
            
        except Exception as e:
            print(f"💥 ERROR: {e}")
            return []
        finally:
            await browser.close()

async def get_current_filtered_year(page):
    """
    Dapatkan tahun yang sedang difilter di halaman.
    """
    try:
        # Cari chip year yang active
        active_year_chip = await page.query_selector('.v-chip--active .v-chip__content')
        if active_year_chip:
            year_text = await active_year_chip.inner_text()
            if year_text.isdigit():
                return int(year_text)
        
        # Fallback: cari dari URL atau element lain
        current_url = page.url
        if 'year=' in current_url:
            year_match = re.search(r'year=(\d{4})', current_url)
            if year_match:
                return int(year_match.group(1))
        
        # Default ke tahun terbaru
        return 2024
        
    except Exception as e:
        print(f"❌ Gagal detect tahun: {e}")
        return 2024

async def extract_data_with_year_filter(page, base_url, target_year):
    """
    Extract data anime dengan filter tahun yang spesifik.
    """
    try:
        # Tunggu sampai window.KAA tersedia
        await page.wait_for_function('window.KAA && window.KAA.data', timeout=15000)
        
        # Execute JavaScript dengan FILTER YEAR
        js_code = f"""
        () => {{
            try {{
                if (window.KAA && window.KAA.data && window.KAA.data[0] && window.KAA.data[0].shows) {{
                    const allShows = window.KAA.data[0].shows;
                    console.log('Total shows in KAA:', allShows.length);
                    
                    // FILTER BY YEAR - ini yang penting!
                    const filteredShows = allShows.filter(show => show.year === {target_year});
                    console.log('Shows for year {target_year}:', filteredShows.length);
                    
                    return filteredShows.map(show => ({{
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
                        poster: show.poster || {{}},
                        watch_uri: show.watch_uri || ''
                    }}));
                }}
                return null;
            }} catch (e) {{
                console.error('Error in KAA extraction:', e);
                return null;
            }}
        }}
        """
        
        raw_data = await page.evaluate(js_code)
        
        if not raw_data:
            print(f"❌ Tidak ada data untuk tahun {target_year}")
            return None
        
        print(f"📊 Mendapatkan {len(raw_data)} anime untuk tahun {target_year}")
        
        processed_data = []
        for item in raw_data:
            try:
                # Validasi tahun - pastikan sesuai filter
                if item.get('year') != target_year:
                    continue
                
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
        print(f"❌ Gagal extract data dengan filter: {e}")
        return None

async def scrape_multiple_years():
    """
    Scrape data untuk multiple years secara sequential.
    """
    async with async_playwright() as p:
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
            all_data = []
            
            # Tahun yang ingin di-scrape (dari terbaru)
            target_years = [2024, 2023, 2022, 2021, 2020]
            
            for year in target_years:
                print(f"\n{'='*50}")
                print(f"🎬 MEMPROSES TAHUN: {year}")
                print(f"{'='*50}")
                
                try:
                    # Pergi ke halaman anime
                    await page.goto(f"{base_url}/anime", wait_until="domcontentloaded", timeout=60000)
                    
                    # Apply filter tahun
                    success = await apply_year_filter(page, year)
                    if not success:
                        print(f"❌ Gagal apply filter untuk tahun {year}")
                        continue
                    
                    # Tunggu data load
                    await page.wait_for_selector(".show-item", timeout=15000)
                    
                    # Extract data dengan filter
                    year_data = await extract_data_with_year_filter(page, base_url, year)
                    
                    if year_data:
                        all_data.extend(year_data)
                        print(f"✅ Tahun {year}: {len(year_data)} anime")
                    else:
                        print(f"⚠️  Tidak ada data untuk tahun {year}")
                    
                    # Delay antar request
                    await asyncio.sleep(2)
                    
                except Exception as e:
                    print(f"❌ Gagal proses tahun {year}: {e}")
                    continue
            
            if all_data:
                await save_anime_data(all_data, "multiple_years")
            
            return all_data
            
        except Exception as e:
            print(f"💥 ERROR: {e}")
            return []
        finally:
            await browser.close()

async def apply_year_filter(page, year):
    """
    Apply filter tahun di UI.
    """
    try:
        # Klik tombol Year
        year_btn = await page.query_selector("button:has-text('Year')")
        if not year_btn:
            print("❌ Tombol Year tidak ditemukan")
            return False
        
        await year_btn.click()
        await asyncio.sleep(2)
        
        # Cari dan klik tahun yang diinginkan
        year_option = await page.query_selector(f'.v-chip .v-chip__content:has-text("{year}")')
        if not year_option:
            print(f"❌ Opsi tahun {year} tidak ditemukan")
            # Tutup dropdown
            close_btn = await page.query_selector("button:has-text('Close')")
            if close_btn:
                await close_btn.click()
            return False
        
        await year_option.click()
        await asyncio.sleep(2)
        
        # Tutup dropdown
        close_btn = await page.query_selector("button:has-text('Close')")
        if close_btn:
            await close_btn.click()
        
        await asyncio.sleep(3)  # Tunggu data reload
        return True
        
    except Exception as e:
        print(f"❌ Gagal apply filter: {e}")
        return False

async def save_anime_data(data, source):
    """Save anime data to JSON file."""
    filename = f'anime_data_{source}.json'
    
    try:
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        
        print(f"💾 Data disimpan ke {filename}")
        print(f"📊 Total {len(data)} anime")
        
        # Stats
        years = list(set([d['tahun'] for d in data if d.get('tahun')]))
        print(f"📅 Tahun dalam data: {sorted(years)}")
        
        # Sample data
        if data:
            print(f"\n📝 Sample data:")
            for i, anime in enumerate(data[:3]):
                print(f"  {i+1}. {anime['judul']} ({anime['tahun']}) - {anime['genre'][:2]}")
        
    except Exception as e:
        print(f"❌ Gagal save data: {e}")

async def main():
    """Main function."""
    print("🚀 KICKASS ANIME SCRAPER - YEAR FILTER FIXED")
    print("=" * 60)
    print("Pilih mode:")
    print("1. Scrape tahun saat ini (cepat)")
    print("2. Scrape multiple years (lengkap)")
    print("=" * 60)
    
    # Untuk GitHub Actions, pilih mode 2 (multiple years)
    choice = 2
    
    start_time = datetime.now()
    
    if choice == 1:
        data = await scrape_kickass_anime_all_years()
    else:
        data = await scrape_multiple_years()
    
    end_time = datetime.now()
    duration = (end_time - start_time).total_seconds()
    
    if data:
        print(f"\n🎉 SCRAPING SELESAI!")
        print(f"⏱️  Durasi: {duration:.2f} detik")
        print(f"📊 Total anime: {len(data)}")
        
        # Validasi tahun
        years = list(set([d['tahun'] for d in data]))
        print(f"✅ Tahun yang berhasil di-scrape: {sorted(years)}")
        
    else:
        print("\n❌ SCRAPING GAGAL!")

if __name__ == "__main__":
    asyncio.run(main())
