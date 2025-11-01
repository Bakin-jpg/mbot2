import asyncio
from playwright.async_api import async_playwright
import json
from urllib.parse import urljoin
import re
import os
from datetime import datetime

async def scrape_kickass_anime_all_years():
    """
    Scrape data anime dari kickass-anime.ru untuk SEMUA tahun dari 2000 sampai tahun terakhir.
    Optimized untuk GitHub Actions.
    """
    async with async_playwright() as p:
        # Install browser untuk GitHub Actions
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

            # Dapatkan semua tahun yang tersedia dari dropdown
            available_years = await get_available_years(page)
            if not available_years:
                print("❌ Tidak bisa mendapatkan daftar tahun, menggunakan default 2000-2024")
                available_years = list(range(2000, 2025))
            else:
                # Filter hanya tahun dari 2000 ke atas
                available_years = [year for year in available_years if year >= 2000]
                # URUT DARI TERBARU untuk GitHub Actions
                available_years.sort(reverse=True)

            print(f"📅 Tahun yang akan di-scrape: {available_years}")
            print(f"📊 Total {len(available_years)} tahun")

            all_scraped_data = []
            processed_count = 0

            for year in available_years:
                print(f"\n{'='*60}")
                print(f"🎬 MEMPROSES TAHUN: {year}")
                print(f"{'='*60}")

                try:
                    # Klik tombol Year untuk membuka dropdown
                    year_button = await page.query_selector("button:has-text('Year'), .v-btn:has-text('Year')")
                    if not year_button:
                        print("❌ Tombol Year tidak ditemukan")
                        continue

                    await year_button.click()
                    await asyncio.sleep(2)
                    print("📋 Dropdown Year dibuka")

                    # Pilih tahun yang diinginkan
                    year_option = await page.query_selector(f"button:has-text('{year}')")
                    if not year_option:
                        print(f"❌ Opsi tahun {year} tidak ditemukan")
                        # Tutup dropdown
                        close_btn = await page.query_selector("button:has-text('CLOSE')")
                        if close_btn:
                            await close_btn.click()
                        continue

                    await year_option.click()
                    await asyncio.sleep(2)
                    print(f"✅ Tahun {year} dipilih")

                    # Klik tombol CLOSE
                    close_button = await page.query_selector("button:has-text('CLOSE')")
                    if close_button:
                        await close_button.click()
                        await asyncio.sleep(3)
                        print("🔒 Dialog Year ditutup")
                    else:
                        await page.keyboard.press("Escape")
                        await asyncio.sleep(2)

                    # Tunggu loading anime list
                    try:
                        await page.wait_for_selector(".show-item", timeout=30000)
                        print("📝 Daftar anime dimuat")
                    except:
                        print("⚠️  Timeout menunggu anime list, lanjut...")
                        continue

                    # Scrape anime untuk tahun ini
                    year_scraped_data = await scrape_anime_from_list(page, context, base_url, year)
                    all_scraped_data.extend(year_scraped_data)
                    processed_count += 1

                    print(f"✅ Selesai tahun {year}: {len(year_scraped_data)} anime")

                    # Untuk GitHub Actions, batasi jika terlalu banyak
                    if processed_count >= 3:  # Max 3 tahun per run
                        print(f"🛑 BATAS: Sudah proses {processed_count} tahun, berhenti untuk GitHub Actions")
                        break

                except Exception as e:
                    print(f"❌ Gagal memproses tahun {year}: {e}")
                    continue

            # Simpan data
            if all_scraped_data:
                await save_anime_data(all_scraped_data)
                print(f"\n🎉 HASIL AKHIR: {len(all_scraped_data)} anime dari {processed_count} tahun")

            return all_scraped_data

        except Exception as e:
            print(f"💥 ERROR: {e}")
        finally:
            await browser.close()

async def get_available_years(page):
    """Mendapatkan semua tahun yang tersedia dari dropdown Year."""
    try:
        year_button = await page.query_selector("button:has-text('Year')")
        if not year_button:
            return None

        await year_button.click()
        await asyncio.sleep(2)

        # Ambil semua tombol tahun
        year_buttons = await page.query_selector_all("button")
        years = []
        
        for button in year_buttons:
            text = await button.inner_text()
            year_match = re.search(r'\b(19|20)\d{2}\b', text)
            if year_match:
                years.append(int(year_match.group()))

        # Tutup dialog
        close_btn = await page.query_selector("button:has-text('CLOSE')")
        if close_btn:
            await close_btn.click()
        
        await asyncio.sleep(1)

        # Remove duplicates dan sort
        years = list(set(years))
        years.sort(reverse=True)  # TERBARU DULU
        
        print(f"📅 Tahun tersedia: {years}")
        return years

    except Exception as e:
        print(f"❌ Gagal mendapatkan tahun: {e}")
        return None

async def scrape_anime_from_list(page, context, base_url, year):
    """Scrape semua anime dari halaman list."""
    scraped_data = []
    
    try:
        anime_items = await page.query_selector_all(".show-item")
        print(f"📊 Menemukan {len(anime_items)} anime untuk {year}")

        existing_data = await load_existing_data()

        for index, item in enumerate(anime_items[:10]):  # BATASI 10 anime per tahun untuk GitHub Actions
            print(f"\n--- Anime #{index + 1} ({year}) ---")
            
            try:
                # Ambil poster
                poster_div = await item.query_selector(".v-image__image--cover")
                poster_url = "Tidak tersedia"
                if poster_div:
                    style = await poster_div.get_attribute("style")
                    if style and 'url("' in style:
                        url_match = re.search(r'url\("([^"]+)"\)', style)
                        if url_match:
                            poster_url = urljoin(base_url, url_match.group(1))

                # Ambil URL detail
                detail_link = await item.query_selector("h2.show-title a")
                if not detail_link:
                    continue
                
                detail_url = urljoin(base_url, await detail_link.get_attribute("href"))
                
                # Cek duplikat
                if await is_duplicate(existing_data, detail_url):
                    print(f"⏩ Skip (duplikat): {detail_url}")
                    continue

                # Ambil judul
                title_elem = await item.query_selector("h2.show-title span")
                title = await title_elem.inner_text() if title_elem else "Judul tidak ditemukan"

                # Ambil genre
                genre_elems = await item.query_selector_all(".v-chip--outlined .v-chip__content")
                genres = [await el.inner_text() for el in genre_elems]
                genres = [g for g in genres if not re.match(r'^(19|20)\d{2}$', g) and g not in ['TV', 'SUB', 'DUB']]

                print(f"🎬 {title}")
                print(f"🏷️  {genres}")

                # Scrape detail
                anime_info = await scrape_anime_detail(context, detail_url, base_url, title, genres, poster_url)
                
                if anime_info:
                    anime_info['tahun'] = year
                    scraped_data.append(anime_info)
                    print(f"✅ Berhasil scrape")

            except Exception as e:
                print(f"❌ Gagal: {e}")

    except Exception as e:
        print(f"❌ Gagal scrape list: {e}")

    return scraped_data

async def scrape_anime_detail(context, detail_url, base_url, title, genres, poster_url):
    """Scrape detail anime."""
    detail_page = None
    
    try:
        detail_page = await context.new_page()
        await detail_page.goto(detail_url, timeout=60000)
        await detail_page.wait_for_selector(".anime-info-card", timeout=30000)
        
        # Scrape sinopsis
        synopsis = "Sinopsis tidak ditemukan"
        synopsis_elem = await detail_page.query_selector("div.v-card__title:has-text('Synopsis')")
        if synopsis_elem:
            parent = await synopsis_elem.query_selector("xpath=..")
            text_elem = await parent.query_selector(".text-caption")
            if text_elem:
                synopsis = await text_elem.inner_text()

        # Cari tombol Watch
        watch_btn = await detail_page.query_selector('a.v-btn[href*="/ep-"]')
        watch_url = None
        if watch_btn:
            watch_path = await watch_btn.get_attribute("href")
            watch_url = urljoin(base_url, watch_path)

        # Ambil iframe sederhana
        iframe_src = "Iframe tidak diambil"  # Skip iframe untuk efisiensi

        anime_info = {
            "judul": title.strip(),
            "sinopsis": synopsis.strip(),
            "genre": genres,
            "url_poster": poster_url,
            "url_detail": detail_url,
            "url_watch": watch_url,
            "iframe_url": iframe_src,
            "tahun": None,
            "last_updated": datetime.now().isoformat()
        }
        
        await detail_page.close()
        return anime_info

    except Exception as e:
        print(f"❌ Gagal scrape detail: {e}")
        if detail_page:
            await detail_page.close()
        return None

async def load_existing_data():
    """Load data existing."""
    try:
        if os.path.exists('anime_data_all_years.json'):
            with open('anime_data_all_years.json', 'r', encoding='utf-8') as f:
                return json.load(f)
    except:
        pass
    return []

async def is_duplicate(existing_data, detail_url):
    """Cek duplikat."""
    return any(anime.get('url_detail') == detail_url for anime in existing_data)

async def save_anime_data(new_data):
    """Simpan data dengan merge existing."""
    existing_data = await load_existing_data()
    
    # Gabungkan data
    existing_urls = {anime['url_detail'] for anime in existing_data}
    final_data = existing_data.copy()
    
    for anime in new_data:
        if anime['url_detail'] not in existing_urls:
            final_data.append(anime)
    
    # Simpan
    with open('anime_data_all_years.json', 'w', encoding='utf-8') as f:
        json.dump(final_data, f, ensure_ascii=False, indent=2)
    
    print(f"💾 Data tersimpan: {len(final_data)} total anime")

async def main():
    """Fungsi utama."""
    print("🚀 SCRAPER KICKASS ANIME - GITHUB ACTION OPTIMIZED")
    print("=" * 60)
    print("Fitur:")
    print("• Auto-detect semua tahun (2000-sekarang)")
    print("• Urut dari TERBARU (prioritas tahun baru)") 
    print("• Batasi 3 tahun & 10 anime/tahun (GitHub Actions)")
    print("• Skip duplikat otomatis")
    print("=" * 60)
    
    await scrape_kickass_anime_all_years()

if __name__ == "__main__":
    asyncio.run(main())
