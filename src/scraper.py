import threading
import os
import random
import re
import json
from typing import Dict, List
from pptx import Presentation
import pdfkit

import requests
import yaml
from bs4 import BeautifulSoup
from course import CMSFile, Course
from requests_ntlm import HttpNtlmAuth
from tqdm import tqdm

from auth import Credentials, CMSAuthenticationError

YML_FILE = "config.yml"
YML_CONFIG = yaml.safe_load(open(YML_FILE))

HOST = YML_CONFIG["host"]
DOWNLOADS_DIR = YML_CONFIG["downloads_dir"]

TQDM_COLORS = [
    "#ff0000",
    "#00ff00",
    "#0000ff",
    "#ffff00",
    "#00ffff",
    "#ff00ff",
    "#ffffff",
    "#000000",
]


class Scraper:
    """
    Class for scraping data from GUC CMS.
    """

    def __init__(self, credentials: Credentials):
        self.credentials: Credentials = credentials
        self.session: requests.Session = requests.Session()
        self.session.auth = HttpNtlmAuth(credentials.username, credentials.password)
        self.session.headers.update({"User-Agent": "Mozilla/5.0"})
        self.html_parser: str = "html.parser"
        self.get_args: Dict[str, object] = {
            "auth": self.session.auth,
            "verify": False,
        }

    @property
    def home_soup(self) -> BeautifulSoup:
        """
        Get home page.
        """
        return BeautifulSoup(self.session.get(HOST, **self.get_args).text, self.html_parser)

    def run(self) -> None:
        """
        Run the scraper.
        """

        # authenticate
        try:
            self.authenticate()
        except CMSAuthenticationError:
            self.credentials.remove_credentials()
            return self.run()

        self.__scrap_courses()

        self.__scrap_files()

        self.__create_courses_dir()

        self.__download_all_files()

    def __download_all_files(self):
        # download files in parallel using threads
        threads = []
        for file in self.files:
            thread = threading.Thread(target=self.__download_file, args=(file,))
            thread.start()
            threads.append(thread)

    def __create_courses_dir(self):
        for course in self.courses:
            course.create_course_directory()

    def __scrap_courses(self) -> None:
        # cache the courses name and links
        if os.path.exists(".courses.json"):
            self.__get_cached_courses()
        else:
            self.__cache_courses()

    def __cache_courses(self):
        self.course_names = self.__get_course_names()
        self.courses = self.__get_available_courses()
        self._populate_courses_data()
        with open(".courses.json", "w") as f:
            data = {course.course_text: course.course_url for course in self.courses}
            json.dump(data, f, indent=4)

    def __get_cached_courses(self):
        with open(".courses.json", "r") as f:
            courses_data = json.load(f)
            courses = []
            for course_text in courses_data:
                link = courses_data[course_text]
                course = Course(course_url=link)
                course.set_course_text(course_text)
                courses.append(course)
            self.courses = courses
            self.course_names = list(courses_data.keys())
            self.courses_links = list(courses_data.values())
            self._populate_courses_data()

    def __scrap_files(self):
        for course in self.courses:
            course.get_course_files(os.path.join(DOWNLOADS_DIR, course.__str__()))

    def _populate_courses_data(self):
        # populate courses with names
        for course, course_text in zip(self.courses, self.course_names):
            course.set_course_text(course_text)

        # populate courses soups
        self.get_courses_soup()

    def authenticate(self) -> None:
        """
        Authenticate with GUC CMS.
        """
        response = self.session.get(HOST, **self.get_args)
        if response.status_code != 200:
            raise CMSAuthenticationError("Authentication failed.")

    def __get_available_courses(self) -> List[Course]:
        """
        Get list of courses.
        """
        self.courses_links = [link.get("href") for link in self.home_soup.find_all("a") if link.get("href")]
        self.courses_links = [
            HOST + link for link in self.courses_links if re.match(r"\/apps\/student\/CourseViewStn\?id(.*)", link)
        ]
        return [Course(link) for link in self.courses_links]

    def __get_course_names(self) -> List[str]:
        "get course names"
        courses_table = list(
            self.home_soup.find(
                "table",
                {"id": "ContentPlaceHolderright_ContentPlaceHoldercontent_GridViewcourses"},
            )
        )
        return [
            re.sub(
                Course.get_course_regex(),
                r"\1-\2",
                courses_table[i].text.strip(),
            ).strip()
            for i in range(2, len(courses_table) - 1)
        ]

    def get_courses_soup(self) -> None:
        """
        Get courses page.
        """
        for course in self.courses:
            course.set_course_soup(
                BeautifulSoup(
                    self.session.get(course.course_url, **self.get_args).text,
                    self.html_parser,
                )
            )

    def __download_file(self, file: CMSFile) -> None:
        response = self.session.get(file.url, **self.get_args, stream=True, allow_redirects=True)
        if response.status_code != 200:
            raise CMSAuthenticationError("Authentication failed.")

        total_size = int(response.headers.get("Content-Length"))

        with open(file.path, "wb") as f:
            with tqdm(
                total=total_size,
                unit="B",
                unit_scale=True,
                desc=file.path,
                initial=0,
                dynamic_ncols=True,
                colour=random.choice(TQDM_COLORS),
            ) as t:
                for chunk in response.iter_content(chunk_size=1024):
                    f.write(chunk)
                    t.update(len(chunk))

        if file.extension == 'pptx':
            if os.path.exists(file.path):
                try:
                    presentation = Presentation(file.path)
                    pdf_path = file.path.replace('.pptx', '.pdf')
                    pdfkit.from_file(file.path, pdf_path)
                except Exception as e:
                    print(f"Error converting {file.path} to PDF: {e}")
            else:
                print(f"File {file.path} does not exist.")

    @property
    def files(self) -> List[CMSFile]:
        """
        Get all files.
        """
        return [file for course in self.courses for file in course.files if not os.path.exists(file.path)]