import requests
from bs4 import BeautifulSoup
from typing import Tuple, List, Type, Optional, Dict
import os
from requests_ntlm import HttpNtlmAuth
import re
from getpass import getpass
import yaml
from contextlib import suppress
from sanitize_filename import sanitize


YML_FILE = "config.yml"
YML_CONFIG = yaml.safe_load(open(YML_FILE))
HOST = YML_CONFIG["host"]
DOWNLOADS_DIR = YML_CONFIG["downloads_dir"]


class CMSAuthenticationError(Exception):
    """ The CMSAuthenticationError class is raised when the user's credentials are invalid.
    """

    def __init__(self, message: Optional[str] = None) -> None:
        self.message = message
        if message is None:
            self.message = "Authentication failed."
        super().__init__(self.message)

    def __str__(self) -> str:
        return self.message


class Credentials:
    """ Credentials  management. """

    def __init__(self):
        self.filename = ".env"
        print("Reading credentials ...")
        if os.path.exists(self.filename):
            self.__get_credentials_from_env()
        else:
            self.__get_credentials_from_input()
            self.__save_credentials()

    def __str__(self) -> str:
        return f"{self.username}:{'*'*len(self.password)}"

    def __get_credentials_from_env(self) -> None:
        """
        Get credentials from file.
        """
        with open(self.filename, "r") as f:
            lines = f.readlines()
            self.username = lines[0].strip()
            self.password = lines[1].strip()

    def __save_credentials(self) -> None:
        """
        Save credentials to file.
        """
        with open(self.filename, "w") as f:
            f.write(f"{self.username}\n{self.password}")

    def __get_credentials_from_input(self) -> None:
        """
        Get credentials from input.
        """
        self.username = input("GUC Username: ")
        self.password = getpass(prompt="GUC Password: ")
        try:
            Scraper(credentials=self).authenticate()
            return
        except CMSAuthenticationError:
            print("Authentication failed. Please try again.")
            self.__get_credentials_from_input()

    def remove_credentials(self) -> None:
        """
        Remove credentials file.
        """
        os.remove(self.filename)
        print("Credentials removed.")


class Course:
    """
    Class for storing course information.
    """

    def __init__(self, course_url: str, scraper: "Scraper") -> None:
        self.course_url = course_url
        self.id = self.course_url.split("id")[1][1:].split("&")[0]
        self.files = []

    def __str__(self) -> str:
        return f"[{self.course_code}] {self.course_name}"

    __repr__ = __str__

    @staticmethod
    def get_course_regex() -> re.Pattern:
        return re.compile(r"\n*[\(][\|]([^\|]*)[\|][\)]([^\(]*)[\(].*\n*")

    def set_course_code(self, course_text: str) -> None:
        self.course_code = course_text.split("-")[0].strip()

    def set_course_name(self, course_text: str) -> None:
        self.course_name = course_text.split("-")[1].strip()

    def create_course_directory(self) -> None:
        course_dir = os.path.join(DOWNLOADS_DIR, sanitize(self.__str__()))
        os.makedirs(course_dir, exist_ok=True)

    def set_course_soup(self, course_soup: BeautifulSoup) -> None:
        self.course_soup = course_soup

    def get_course_files(self) -> List[str]:
        """
        Get the list of files in the course.
        """
        files_body = self.course_soup.find_all(class_="card-body")

        for item in files_body:
            self.files.append((CMSFile(soup=item)))


class CMSFile:
    """ a cms file object"""

    def __init__(self, soup: BeautifulSoup) -> None:
        self.soup = soup
        self.url = HOST + self.soup.find("a")["href"]
        self.week = self.soup.parent.parent.parent.parent.find(
            "h2").text.strip()
        self.description = re.sub(self.get_file_regex(
        ), '\\1', self.soup.find('div').text).strip()
        self.name = re.sub(self.get_file_regex(), '\\1',
                           self.soup.find('strong').text).strip()

    @staticmethod
    def get_file_regex() -> re.Pattern:
        return re.compile(r'[0-9]* - (.*)')

    def __str__(self) -> str:
        return f"{self.name}"

    __repr__ = __str__

    @property
    def path(self) -> str:
        self.week = sanitize(self.week)
        self.extension = self.url.rsplit(".", 1)[1]
        self.name = sanitize(self.name)
        return os.path.join(DOWNLOADS_DIR, self.week, f"{self.name}.{self.extension}")


class Scraper:
    """
    Class for scraping data from GUC CMS.
    """

    def __init__(self, credentials: Credentials):
        self.credentials: Credentials = credentials
        self.session: requests.Session = requests.Session()
        self.session.auth = HttpNtlmAuth(
            credentials.username, credentials.password)
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
        try:
            self.authenticate()
        except CMSAuthenticationError as e:
            self.credentials.remove_credentials()
            return

        self.course_names = self.__get_course_names()
        self.courses = self.__get_available_courses()

        for course, course_name in zip(self.courses, self.course_names):
            course.set_course_code(course_name)
            course.set_course_name(course_name)

        for course in self.courses:
            course.create_course_directory()

        self.get_courses_soup()

        for course in self.courses:
            course.get_course_files()

        for course in self.courses:
            for file in course.files:
                print(f"Downloading {file.path}")

    def authenticate(self) -> None:
        """
        Authenticate with GUC CMS.
        """
        response = self.session.get(HOST, **self.get_args)
        if response.status_code != 200:
            raise CMSAuthenticationError("Authentication failed.")

    def __get_available_courses(self) -> Type[List[Course]]:
        """
        Get list of courses.
        """
        courses_links = [
            link.get("href") for link in self.home_soup.find_all("a") if link.get("href")
        ]
        courses_links = [
            HOST + link
            for link in courses_links
            if re.match(r"\/apps\/student\/CourseViewStn\?id(.*)", link)
        ]
        return [Course(link, self) for link in courses_links]

    def __get_course_names(self) -> List[str]:
        "get course names"
        courses_table = list(
            self.home_soup.find(
                "table",
                {
                    "id": "ContentPlaceHolderright_ContentPlaceHoldercontent_GridViewcourses"
                }
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
            course.set_course_soup(BeautifulSoup(
                self.session.get(course.course_url, **
                                 self.get_args).text, self.html_parser
            ))
