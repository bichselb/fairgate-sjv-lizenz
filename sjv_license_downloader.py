# SJV License Downloader
# Copyright (C) 2024 Beni Bichsel

# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published
# by the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.

# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.


import os
import time
import argparse
from datetime import datetime
import tempfile

from tqdm import tqdm
import fitz  # PyMuPDF
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.remote.webdriver import WebDriver
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from selenium.common.exceptions import NoSuchElementException, ElementClickInterceptedException, ElementNotInteractableException


script_directory = os.path.dirname(os.path.realpath(__file__))
downloads_directory = os.path.join(script_directory, 'downloads')
timestamp = datetime.now().strftime("%Y-%m-%d-%H-%M-%S-%f")
downloads_directory = tempfile.mkdtemp(dir=downloads_directory, prefix=timestamp + '_')
combined_file = os.path.join(downloads_directory, '1_all.pdf')


class LicenseDownloader:

    def __init__(self, driver: WebDriver, club_name: str):
        self.driver = driver
        self.wait = WebDriverWait(self.driver, 10)
        self.club_name = club_name

    def login(self, username: str, password: str):
        print('Logging in with user:', username)
        self.driver.get(f"https://mein.fairgate.ch/{self.club_name}/backend/signin")

        username_field = self.wait.until(EC.presence_of_element_located((By.ID, "username")))
        password_field = self.driver.find_element(By.ID, "password")

        username_field.send_keys(username)
        password_field.send_keys(password)

        submit_button = self.driver.find_element(By.NAME, "_submit")
        submit_button.click()

        self.close_popups()
    
    def close_popups(self):
        print('Closing popups (if any)')
        while True:
            time.sleep(4) # pop-up does not load immediately
            try:
                close_button = self.driver.find_element(By.CLASS_NAME, "fg-dev-close-window")
                close_button.click()

            except (NoSuchElementException, ElementClickInterceptedException, ElementNotInteractableException):
                break
    
    def get_user_pages(self):
        print('Collecting the pages of all users')

        self.driver.get(f"https://mein.fairgate.ch/{self.club_name}/backend/contact/list")
        user_pages: list[str] = []

        while True:
            self.close_popups()
            
            contact_links = self.wait.until(EC.presence_of_all_elements_located((By.CLASS_NAME, "fg-dev-contactname")))

            for link in contact_links:
                href = link.get_attribute("href")
                if href:
                    user_pages.append(href)
        
            print('Going to next page')
            next_button = self.driver.find_element(By.ID, "DataTables_Table_0_next")
            classes = next_button.get_attribute('class')
            if classes is not None and 'disabled' in classes:
                break
            else:
                next_button.click()
        
        return user_pages
            
    def download_licenses(self, user_pages: list[str]):
        print('Downloading licenses')
        progress_bar = tqdm(user_pages)
        for user_page in progress_bar:
            self.driver.get(user_page)

            self.close_popups()

            element = self.wait.until(EC.presence_of_element_located((By.CLASS_NAME, "page-title-sub")))
            person = element.text
            progress_bar.set_description('License for ' + person)

            try:
                download = self.driver.find_element(By.XPATH, "//a[contains(., 'Download Lizenz')]")
                download.click()
            except NoSuchElementException:
                print(f"No license available for {person}")
    
    def logout(self):
        print('Logging out')
        self.driver.get(f"https://mein.fairgate.ch/{self.club_name}/backend/signout")


def concatenate_pdfs(input_dir: str, output_pdf: str):
    # Create a new empty PDF
    merged_document = fitz.open()

    # Get list of all PDF files in the input directory
    pdf_files = [os.path.join(input_dir, f) for f in os.listdir(input_dir) if f.endswith('.pdf')]

    # Sort PDF files by name (optional)
    pdf_files.sort()

    # Append each PDF to the merged_document
    for pdf_file in pdf_files:
        with fitz.open(pdf_file) as document:
            merged_document.insert_pdf(document)

    # Save the merged and compressed PDF
    merged_document.save(output_pdf, garbage=4, deflate=True, clean=True, deflate_images=True, deflate_fonts=True)

    print(f'Merged and compressed PDF saved to: {output_pdf}')


def get_args():
    parser = argparse.ArgumentParser(description="Download all SJV licenses from Fairgate")
    parser.add_argument('--club_name', type=str, help='Club name according to fairgate url: https://mein.fairgate.ch/club_name')
    parser.add_argument('--username', type=str, help='Fairgate username')
    parser.add_argument('--password', type=str, help='Fairgate password')
    parser.add_argument('--download-directory', type=str, help='Directory to store the licenses', default=downloads_directory)
    parser.add_argument('--combined_file', type=str, help='File to write a summary file of all licenses to', default=combined_file)
    args = parser.parse_args()

    os.makedirs(args.download_directory, exist_ok=True)
    return args


def main():
    args = get_args()

    chrome_options = Options()
    chrome_options.add_experimental_option('prefs', {
        'download.default_directory': args.download_directory
    })
    driver = webdriver.Chrome(service=Service(), options=chrome_options)

    downloader = LicenseDownloader(driver, args.club_name)

    downloader.login(args.username, args.password)
    user_pages = downloader.get_user_pages()
    downloader.download_licenses(user_pages)
    downloader.logout()
    driver.close()

    concatenate_pdfs(downloads_directory, args.combined_file)


if __name__ == '__main__':
    main()
