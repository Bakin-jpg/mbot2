import asyncio
from playwright.async_api import async_playwright
import json
from urllib.parse import urljoin, urlparse, parse_qs, urlencode
import re
import os
from datetime import datetime

async def scrape_kickass_anime_all_years():
    """
    Scrape data anime dari kickass-anime.ru untuk SEMUA tahun dari 2000 sampai tahun terakhir.
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
            await page.goto(base_url, timeout=90000, wait_until="domcontentloaded")
            print("Berhasil membuka halaman anime.")

            # Dapatkan semua tahun yang tersedia dari dropdown
            available_years = await get_available_years(page)
            if not available_years:
                print("Tidak bisa mendapatkan daftar tahun, menggunakan default 2000-2024")
                available_years = list(range(2000, 2025))
            else:
                # Filter hanya tahun dari 2000 ke atas
                available_years = [year for year in available_years if year >= 2000]
                available_years.sort(reverse=True)  # Urutkan dari tahun terbaru

            print(f"Tahun yang akan di-scrape: {available_years}")

            all_scraped_data = []

            for year in available_years:
                print(f"\n{'='*60}")
                print(f"MEMPROSES TAHUN: {year}")
                print(f"{'='*60}")

                try:
                    # Klik tombol Year untuk membuka dropdown
                    year_button_selectors = [
                        "button:has-text('Year')",
                        ".v-btn:has-text('Year')",
                        "//button[contains(., 'Year')]"
                    ]
                    
                    year_button = None
                    for selector in year_button_selectors:
                        if selector.startswith("//"):
                            year_button = await page.query_selector(f"xpath={selector}")
                        else:
                            year_button = await page.query_selector(selector)
                        if year_button:
                            break
                    
                    if not year_button:
                        print("Tombol Year tidak ditemukan")
                        continue

                    await year_button.click()
                    await page.wait_for_timeout(2000)
                    print("Dropdown Year dibuka")

                    # Pilih tahun yang diinginkan
                    year_option_selectors = [
                        f"//div[contains(@class, 'v-dialog__content')]//button[contains(., '{year}')]",
                        f".v-dialog__content button:has-text('{year}')",
                        f"//button[text()='{year}']"
                    ]
                    
                    year_option = None
                    for selector in year_option_selectors:
                        if selector.startswith("//"):
                            year_option = await page.query_selector(f"xpath={selector}")
                        else:
                            year_option = await page.query_selector(selector)
                        if year_option:
                            break
                    
                    if not year_option:
                        print(f"Opsi tahun {year} tidak ditemukan")
                        # Tutup dropdown jika tahun tidak ditemukan
                        close_button = await page.query_selector("button:has-text('CLOSE'), .v-btn:has-text('CLOSE')")
                        if close_button:
                            await close_button.click()
                            await page.wait_for_timeout(1000)
                        continue

                    await year_option.click()
                    await page.wait_for_timeout(2000)
                    print(f"Tahun {year} dipilih")

                    # Klik tombol CLOSE untuk menutup dialog
                    close_button = await page.query_selector("button:has-text('CLOSE'), .v-btn:has-text('CLOSE')")
                    if close_button:
                        await close_button.click()
                        await page.wait_for_timeout(3000)
                        print("Dialog Year ditutup")
                    else:
                        print("Tombol CLOSE tidak ditemukan, menggunakan Escape")
                        await page.keyboard.press("Escape")
                        await page.wait_for_timeout(2000)

                    # Tunggu loading anime list
                    await page.wait_for_selector(".show-item", timeout=30000)
                    print("Daftar anime untuk tahun ini dimuat")

                    # Scrape semua anime di halaman ini untuk tahun tersebut
                    year_scraped_data = await scrape_anime_from_list(page, context, base_url, year)
                    all_scraped_data.extend(year_scraped_data)

                    print(f"✓ Selesai memproses tahun {year}: {len(year_scraped_data)} anime")

                except Exception as e:
                    print(f"!!! Gagal memproses tahun {year}: {type(e).__name__}: {e}")
                    continue

            # Simpan semua data
            if all_scraped_data:
                # Load existing data jika ada
                existing_data = []
                if os.path.exists('anime_data_all_years.json'):
                    with open('anime_data_all_years.json', 'r', encoding='utf-8') as f:
                        existing_data = json.load(f)
                    print(f"Data existing ditemukan: {len(existing_data)} anime")

                # Gabungkan data baru dengan existing
                updated_urls = [anime['url_detail'] for anime in all_scraped_data]
                final_data = all_scraped_data.copy()
                
                for existing_anime in existing_data:
                    if existing_anime['url_detail'] not in updated_urls:
                        final_data.append(existing_anime)

                with open('anime_data_all_years.json', 'w', encoding='utf-8') as f:
                    json.dump(final_data, f, ensure_ascii=False, indent=4)
                
                print(f"\n{'='*60}")
                print(f"HASIL AKHIR SCRAPING SEMUA TAHUN:")
                print(f"Total anime: {len(final_data)}")
                print(f"Tahun yang diproses: {available_years}")
                print(f"File: anime_data_all_years.json")
                print(f"{'='*60}")

            return all_scraped_data

        except Exception as e:
            print(f"Terjadi kesalahan fatal: {type(e).__name__}: {e}")
        finally:
            await browser.close()

async def get_available_years(page):
    """
    Mendapatkan semua tahun yang tersedia dari dropdown Year.
    """
    try:
        # Klik tombol Year untuk membuka dropdown
        year_button_selectors = [
            "button:has-text('Year')",
            ".v-btn:has-text('Year')", 
            "//button[contains(., 'Year')]"
        ]
        
        year_button = None
        for selector in year_button_selectors:
            if selector.startswith("//"):
                year_button = await page.query_selector(f"xpath={selector}")
            else:
                year_button = await page.query_selector(selector)
            if year_button:
                break
        
        if not year_button:
            print("Tombol Year tidak ditemukan untuk mendapatkan daftar tahun")
            return None

        await year_button.click()
        await page.wait_for_timeout(2000)

        # Cari dialog yang berisi daftar tahun
        year_dialog_selectors = [
            "//div[contains(@class, 'v-dialog__content')]",
            ".v-dialog__content",
            "//div[contains(@class, 'v-dialog')]"
        ]
        
        year_dialog = None
        for selector in year_dialog_selectors:
            if selector.startswith("//"):
                year_dialog = await page.query_selector(f"xpath={selector}")
            else:
                year_dialog = await page.query_selector(selector)
            if year_dialog:
                break

        if not year_dialog:
            print("Dialog tahun tidak ditemukan")
            return None

        # Ambil semua tombol tahun dari dialog
        year_buttons = await year_dialog.query_selector_all("button")
        years = []
        
        for button in year_buttons:
            text = await button.inner_text()
            # Coba parsing tahun dari teks
            try:
                # Cari angka 4 digit (tahun)
                year_match = re.search(r'\b(19|20)\d{2}\b', text)
                if year_match:
                    year = int(year_match.group())
                    years.append(year)
            except:
                continue

        # Tutup dialog
        close_button = await page.query_selector("button:has-text('CLOSE'), .v-btn:has-text('CLOSE')")
        if close_button:
            await close_button.click()
        else:
            await page.keyboard.press("Escape")
        
        await page.wait_for_timeout(1000)

        # Remove duplicates dan sort
        years = list(set(years))
        years.sort(reverse=True)
        
        print(f"Tahun yang tersedia: {years}")
        return years

    except Exception as e:
        print(f"Gagal mendapatkan daftar tahun: {e}")
        return None

async def scrape_anime_from_list(page, context, base_url, year):
    """
    Scrape semua anime dari halaman list yang sedang aktif.
    """
    scraped_data = []
    
    try:
        # Dapatkan semua item anime di halaman
        anime_items = await page.query_selector_all(".show-item")
        print(f"Menemukan {len(anime_items)} anime untuk tahun {year}")

        # Load existing data untuk pengecekan duplikat
        existing_data = []
        if os.path.exists('anime_data_all_years.json'):
            with open('anime_data_all_years.json', 'r', encoding='utf-8') as f:
                existing_data = json.load(f)

        for index, item in enumerate(anime_items):
            print(f"\n--- Memproses Anime #{index + 1} untuk tahun {year} ---")
            
            try:
                # Ambil URL Poster
                await item.scroll_into_view_if_needed()
                poster_url = "Tidak tersedia"
                
                poster_div = await item.query_selector(".v-image__image--cover")
                if poster_div:
                    poster_style = await poster_div.get_attribute("style")
                    if poster_style and 'url("' in poster_style:
                        parts = poster_style.split('url("')
                        if len(parts) > 1:
                            poster_url_path = parts[1].split('")')[0]
                            poster_url = urljoin(base_url, poster_url_path)
                
                print(f"URL Poster: {poster_url}")

                # Ambil URL detail anime
                detail_link_element = await item.query_selector("h2.show-title a")
                if not detail_link_element:
                    print("Gagal menemukan link detail, melewati item ini.")
                    continue
                
                detail_url_path = await detail_link_element.get_attribute("href")
                full_detail_url = urljoin(base_url, detail_url_path)
                
                # Cek apakah anime sudah ada di data existing
                existing_anime = None
                for anime in existing_data:
                    if anime.get('url_detail') == full_detail_url:
                        existing_anime = anime
                        print(f"Anime sudah ada di data existing: {anime.get('judul')}")
                        break

                if existing_anime:
                    # Jika sudah ada, skip scraping detail lengkap
                    scraped_data.append(existing_anime)
                    continue

                # Ambil judul dari halaman list (lebih cepat)
                title_element = await item.query_selector("h2.show-title span")
                title = await title_element.inner_text() if title_element else "Judul tidak ditemukan"

                # Ambil genre/tags dari halaman list
                genre_elements = await item.query_selector_all(".v-chip--outlined .v-chip__content")
                all_tags = [await el.inner_text() for el in genre_elements]
                irrelevant_tags = ['TV', 'PG-13', 'Airing', '23 min', '24 min', 'SUB', 'DUB', 'ONA']
                # Filter out tahun-tahun dari tags
                genres = [tag for tag in all_tags if tag not in irrelevant_tags and not tag.startswith('EP') and not re.match(r'^(19|20)\d{2}$', tag)]

                print(f"Judul: {title}")
                print(f"Genre: {genres}")

                # Scrape detail lengkap
                anime_info = await scrape_anime_detail(context, full_detail_url, base_url, title, genres, poster_url)
                
                if anime_info:
                    anime_info['tahun'] = year
                    scraped_data.append(anime_info)
                    print(f"✓ Data {title} berhasil di-scrape")

            except Exception as e:
                print(f"!!! Gagal memproses anime #{index + 1}: {type(e).__name__}: {e}")

    except Exception as e:
        print(f"Gagal scrape anime dari list: {e}")

    return scraped_data

async def scrape_anime_detail(context, detail_url, base_url, title, genres, poster_url):
    """
    Scrape detail lengkap anime dari halaman detail.
    """
    detail_page = None
    watch_page = None
    
    try:
        # Buka halaman detail
        detail_page = await context.new_page()
        await detail_page.goto(detail_url, timeout=90000)
        await detail_page.wait_for_selector(".anime-info-card", timeout=30000)
        
        # Scrape informasi dasar
        title_element = await detail_page.query_selector(".anime-info-card .v-card__title span")
        title = await title_element.inner_text() if title_element else title

        # Scrape sinopsis
        synopsis_card_title = await detail_page.query_selector("div.v-card__title:has-text('Synopsis')")
        synopsis = "Sinopsis tidak ditemukan"
        if synopsis_card_title:
            parent_card = await synopsis_card_title.query_selector("xpath=..")
            synopsis_element = await parent_card.query_selector(".text-caption")
            if synopsis_element:
                synopsis = await synopsis_element.inner_text()
        
        # Scrape metadata
        metadata_selector = ".anime-info-card .d-flex.mb-3, .anime-info-card .d-flex.mt-2.mb-3"
        metadata_container = await detail_page.query_selector(metadata_selector)
        metadata = []
        if metadata_container:
            metadata_elements = await metadata_container.query_selector_all(".text-subtitle-2")
            all_meta_texts = [await el.inner_text() for el in metadata_elements]
            metadata = [text.strip() for text in all_meta_texts if text and text.strip() != 'â€¢']

        # Cari tombol "Watch Now" dan ambil URL watch
        watch_button = await detail_page.query_selector('a.v-btn[href*="/ep-"]')
        watch_url = None
        if watch_button:
            watch_url_path = await watch_button.get_attribute("href")
            watch_url = urljoin(base_url, watch_url_path)
            print(f"URL Watch ditemukan: {watch_url}")
        else:
            print("Tombol Watch Now tidak ditemukan")
            await detail_page.close()
            return None

        # Scrape iframe (sederhana saja untuk efisiensi)
        watch_page = await context.new_page()
        await watch_page.goto(watch_url, timeout=90000)
        await watch_page.wait_for_selector(".player-container", timeout=30000)
        
        # Ambil iframe utama saja
        iframe_element = await watch_page.query_selector("iframe.player")
        iframe_src = await iframe_element.get_attribute("src") if iframe_element else "Iframe tidak ditemukan"

        anime_info = {
            "judul": title.strip(),
            "sinopsis": synopsis.strip(),
            "genre": genres,
            "metadata": metadata,
            "url_poster": poster_url,
            "url_detail": detail_url,
            "url_watch": watch_url,
            "iframe_url": iframe_src,
            "tahun": None,
            "last_updated": datetime.now().isoformat()
        }
        
        await detail_page.close()
        await watch_page.close()
        return anime_info

    except Exception as e:
        print(f"Gagal scrape detail anime: {e}")
        if detail_page and not detail_page.is_closed():
            await detail_page.close()
        if watch_page and not watch_page.is_closed():
            await watch_page.close()
        return None

async def main():
    """
    Fungsi utama untuk menjalankan scraping semua tahun.
    """
    print("SCRAPER KICKASS ANIME - SEMUA TAHUN (2000-SEKARANG)")
    print("=" * 60)
    print("Script akan otomatis:")
    print("- Mendeteksi semua tahun yang tersedia")
    print("- Memproses dari tahun terbaru ke terlama")  
    print("- Skip anime yang sudah ada di database")
    print("- Menyimpan progress ke anime_data_all_years.json")
    print("=" * 60)
    
    input("Tekan Enter untuk memulai scraping...")
    
    await scrape_kickass_anime_all_years()

if __name__ == "__main__":
    asyncio.run(main())
