import asyncio
from playwright.async_api import async_playwright
import json
from urllib.parse import urljoin
import os
import sys

async def get_available_years(page):
    """Detect tahun yang tersedia di filter secara otomatis"""
    print("🔍 Mendeteksi tahun yang tersedia...")
    
    try:
        # Klik filter Year untuk membuka dropdown
        year_button = await page.query_selector(".v-btn:has-text('Year')")
        if year_button:
            await year_button.click()
            await asyncio.sleep(2)
            
            # Tunggu dropdown muncul
            await page.wait_for_selector(".v-list-item", timeout=10000)
            
            # Ambil semua item di dropdown
            year_items = await page.query_selector_all(".v-list-item")
            available_years = []
            
            for item in year_items:
                year_text = await item.inner_text()
                year_text = year_text.strip()
                
                # Filter hanya yang angka dan dalam range reasonable
                if year_text.isdigit():
                    year_num = int(year_text)
                    if 1960 <= year_num <= 2030:  # Range reasonable untuk anime
                        available_years.append(year_num)
            
            # Urutkan tahun
            available_years.sort()
            print(f"✅ Tahun tersedia: {available_years}")
            
            # Tutup dropdown
            await page.keyboard.press("Escape")
            await asyncio.sleep(1)
            
            return available_years
            
    except Exception as e:
        print(f"❌ Gagal detect tahun: {e}")
    
    # Fallback: return default years
    default_years = list(range(2000, 2026))
    print(f"⚠️  Menggunakan tahun default: {default_years}")
    return default_years

async def scrape_kickass_anime_by_year():
    """
    Scrape data anime lengkap dari kickass-anime.ru berdasarkan tahun.
    Auto-detect tahun yang tersedia.
    """
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/108.0.0.0 Safari/537.36",
            viewport={'width': 1920, 'height': 1080}
        )
        page = await context.new_page()

        try:
            base_url = "https://kickass-anime.ru/anime"
            await page.goto(base_url, timeout=120000, wait_until="domcontentloaded")
            print("✅ Berhasil membuka halaman anime")

            # Tunggu filter tahun muncul
            await page.wait_for_selector(".v-btn:has-text('Year')", timeout=30000)
            print("✅ Filter tahun ditemukan")

            # DETECT TAHUN YANG TERSEDIA
            available_years = await get_available_years(page)
            
            if not available_years:
                print("❌ Tidak ada tahun yang terdeteksi, menggunakan default")
                available_years = list(range(2000, 2026))

            # Load progress scraping sebelumnya
            progress_file = 'scraping_progress.json'
            current_year = available_years[0]  # Mulai dari tahun terkecil
            completed_years = []

            if os.path.exists(progress_file):
                with open(progress_file, 'r', encoding='utf-8') as f:
                    progress = json.load(f)
                
                # Cek tahun terakhir yang di-scrape masih ada di available years
                last_year = progress.get('current_year', available_years[0])
                if last_year in available_years:
                    current_year = last_year
                completed_years = progress.get('completed_years', [])
                
                print(f"🔄 Melanjutkan dari tahun: {current_year}")
            else:
                print(f"🚀 Memulai dari tahun: {current_year}")

            # Load existing data
            existing_data = []
            if os.path.exists('anime_data_by_year.json'):
                with open('anime_data_by_year.json', 'r', encoding='utf-8') as f:
                    existing_data = json.load(f)
                print(f"📊 Data existing: {len(existing_data)} anime")

            scraped_data = existing_data.copy()
            total_scraped_in_session = 0

            # Filter tahun yang belum completed dan masih available
            years_to_scrape = [year for year in available_years if year >= current_year and year not in completed_years]
            
            print(f"📅 Tahun yang akan di-scrape: {years_to_scrape}")
            print(f"🎯 Total tahun: {len(years_to_scrape)}")

            for year_index, year in enumerate(years_to_scrape):
                if year in completed_years:
                    print(f"⏩ Tahun {year} sudah selesai, skip...")
                    continue

                print(f"\n{'='*60}")
                print(f"🎯 MEMPROSES TAHUN: {year} ({year_index + 1}/{len(years_to_scrape)})")
                print(f"{'='*60}")

                # Klik filter Year
                try:
                    year_button = await page.query_selector(".v-btn:has-text('Year')")
                    if year_button:
                        await year_button.click()
                        await asyncio.sleep(2)

                    # Cari dan klik tahun yang diinginkan
                    year_selector = f".v-list-item:has-text('{year}')"
                    await page.wait_for_selector(year_selector, timeout=10000)
                    year_item = await page.query_selector(year_selector)
                    
                    if year_item:
                        await year_item.click()
                        await asyncio.sleep(3)
                        print(f"✅ Filter tahun {year} diterapkan")
                    else:
                        print(f"❌ Tahun {year} tidak ditemukan di dropdown, skip...")
                        completed_years.append(year)
                        continue
                        
                except Exception as e:
                    print(f"❌ Gagal memilih tahun {year}: {e}")
                    completed_years.append(year)
                    continue

                # Tunggu hasil loading
                try:
                    await page.wait_for_selector(".show-item", timeout=30000)
                except:
                    print(f"❌ Timeout menunggu anime untuk tahun {year}")
                    completed_years.append(year)
                    continue

                # Scrape semua halaman untuk tahun ini
                page_number = 1
                has_next_page = True
                year_anime_count = 0
                max_pages_per_year = 20  # Safety limit untuk GitHub Actions

                while has_next_page and page_number <= max_pages_per_year:
                    print(f"\n  📄 Halaman {page_number} - Tahun {year}")

                    # Tunggu item anime muncul
                    try:
                        await page.wait_for_selector(".show-item", timeout=30000)
                    except:
                        print("  ⏰ Timeout menunggu item anime")
                        break

                    # Dapatkan semua item anime di halaman ini
                    anime_items = await page.query_selector_all(".show-item")
                    print(f"  📺 Menemukan {len(anime_items)} anime")

                    if not anime_items:
                        print("  ❌ Tidak ada anime ditemukan")
                        break

                    # Process each anime item
                    for index, item in enumerate(anime_items):
                        print(f"  🎬 Processing {index + 1}/{len(anime_items)}: ", end="")
                        
                        try:
                            # Ambil URL Poster
                            poster_url = "Tidak tersedia"
                            poster_div = await item.query_selector(".v-image__image--cover")
                            if poster_div:
                                poster_style = await poster_div.get_attribute("style")
                                if poster_style and 'url("' in poster_style:
                                    parts = poster_style.split('url("')
                                    if len(parts) > 1:
                                        poster_url_path = parts[1].split('")')[0]
                                        poster_url = urljoin("https://kickass-anime.ru", poster_url_path)

                            # Ambil URL detail dan judul
                            detail_link_element = await item.query_selector("h2.show-title a")
                            if not detail_link_element:
                                print("No detail link")
                                continue
                            
                            detail_url_path = await detail_link_element.get_attribute("href")
                            full_detail_url = urljoin("https://kickass-anime.ru", detail_url_path)
                            
                            # Ambil judul dari halaman utama (lebih cepat)
                            title_element = await item.query_selector("h2.show-title span")
                            title = await title_element.inner_text() if title_element else "Judul tidak ditemukan"
                            
                            print(title)

                            # Cek apakah anime sudah ada
                            existing_anime = None
                            for anime in scraped_data:
                                if anime.get('url_detail') == full_detail_url:
                                    existing_anime = anime
                                    break

                            if existing_anime:
                                year_anime_count += 1
                                continue

                            # Data minimal untuk efisiensi
                            anime_info = {
                                "judul": title.strip(),
                                "tahun": str(year),
                                "url_poster": poster_url,
                                "url_detail": full_detail_url,
                                "scraping_tahun": year,
                                "last_updated": asyncio.get_event_loop().time(),
                                "genre": [],
                                "sinopsis": "",
                                "metadata": []
                            }

                            scraped_data.append(anime_info)
                            year_anime_count += 1
                            total_scraped_in_session += 1

                        except Exception as e:
                            print(f"❌ Error: {e}")

                    # Cek halaman berikutnya
                    try:
                        next_buttons = await page.query_selector_all(".v-pagination__navigation")
                        next_button = None
                        
                        for btn in next_buttons:
                            if await btn.query_selector(".mdi-chevron-right"):
                                is_disabled = await btn.get_attribute("disabled")
                                if not is_disabled:
                                    next_button = btn
                                    break
                        
                        if next_button:
                            page_number += 1
                            await next_button.click()
                            await asyncio.sleep(3)
                            print(f"  ↪️  Pindah ke halaman {page_number}")
                        else:
                            has_next_page = False
                            print(f"  ✅ Selesai halaman terakhir")
                    except Exception as e:
                        has_next_page = False
                        print(f"  ✅ Tidak ada halaman berikutnya: {e}")

                print(f"\n✅ Selesai tahun {year}: {year_anime_count} anime")

                # Tandai tahun ini sebagai selesai
                completed_years.append(year)
                
                # Save progress setelah setiap tahun
                progress_data = {
                    'current_year': year + 1,
                    'completed_years': completed_years,
                    'available_years': available_years,  # Simpan juga available years
                    'total_anime': len(scraped_data),
                    'last_updated': asyncio.get_event_loop().time(),
                    'session_scraped': total_scraped_in_session
                }
                
                with open(progress_file, 'w', encoding='utf-8') as f:
                    json.dump(progress_data, f, ensure_ascii=False, indent=2)

                # Save data sementara
                with open('anime_data_by_year.json', 'w', encoding='utf-8') as f:
                    json.dump(scraped_data, f, ensure_ascii=False, indent=2)

                # Reset filter untuk tahun berikutnya
                try:
                    reset_button = await page.query_selector(".v-btn:has-text('Reset All')")
                    if reset_button:
                        await reset_button.click()
                        await asyncio.sleep(2)
                        print("🔄 Filter direset")
                except:
                    print("⚠️  Gagal reset filter, lanjut...")

                # Check jika sudah mencapai limit GitHub Actions
                if total_scraped_in_session >= 50:  # Safety limit per session
                    print(f"🔄 Sudah scrape {total_scraped_in_session} anime, menyimpan progress...")
                    break

            print(f"\n{'='*60}")
            print(f"🎉 SCRAPING SESSION SELESAI!")
            print(f"📈 Total anime: {len(scraped_data)}")
            print(f"🆕 Anime baru session ini: {total_scraped_in_session}")
            print(f"📅 Tahun selesai: {completed_years}")
            print(f"🎯 Tahun tersedia: {available_years}")
            print(f"{'='*60}")

            # Final save
            with open('anime_data_by_year.json', 'w', encoding='utf-8') as f:
                json.dump(scraped_data, f, ensure_ascii=False, indent=2)

            return len(scraped_data), total_scraped_in_session

        except Exception as e:
            print(f"❌ Terjadi kesalahan fatal: {type(e).__name__}: {e}")
            # Save progress even on error
            if 'current_year' in locals() and 'completed_years' in locals():
                progress_data = {
                    'current_year': current_year,
                    'completed_years': completed_years,
                    'available_years': available_years if 'available_years' in locals() else [],
                    'total_anime': len(scraped_data),
                    'last_updated': asyncio.get_event_loop().time(),
                    'error': str(e)
                }
                with open(progress_file, 'w', encoding='utf-8') as f:
                    json.dump(progress_data, f, ensure_ascii=False, indent=2)
            raise e
        finally:
            await browser.close()

async def main():
    """Main function untuk GitHub Actions"""
    try:
        total_anime, new_anime = await scrape_kickass_anime_by_year()
        
        if new_anime > 0:
            print(f"✅ Success: Added {new_anime} new anime")
            sys.exit(0)
        else:
            print("ℹ️ No new anime added - mungkin sudah up-to-date")
            sys.exit(0)
            
    except Exception as e:
        print(f"❌ Script failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    print("🚀 Starting anime scraping with auto-year detection...")
    asyncio.run(main())
