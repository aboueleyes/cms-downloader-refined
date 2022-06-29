import requests
from bs4 import BeautifulSoup
from typing import Tuple, List, Type, Optional, Dict
import os
from requests_ntlm import HttpNtlmAuth
import re
from getpass import getpass
import yaml


YML_FILE = "config.yml"
YML_CONFIG = yaml.safe_load(open(YML_FILE))
HOST = YML_CONFIG["host"]
DOWNLOADS_DIR = YML_CONFIG["downloads_dir"]


class CMSAuthenticationError(Exception):
    """
    Exception for authentication errors.
    """

    def __init__(self, message: Optional[str] = None) -> None:
        self.message = message
        if message is None:
            self.message = "Authentication failed."
        super().__init__(self.message)

    def __str__(self) -> str:
        return self.message


class Credentials:
    """
    Class for storing credentials.
    """

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
        self.password = getpass("GUC Password: ")
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

    def __init__(self, course_url: str):
        self.course_url = course_url
        self.course_code, self.course_name = self.get_course_info()
        self.id = self.course_url.split("id")[1][1:].split("&")[0]

    def get_course_info(self) -> Tuple[str, str]:
        """
        Get course information from course URL.
        """
        return None, None

    def __str__(self) -> str:
        return f"{self.id}"
        # return f"{self.course_code} - {self.course_name}"

    __repr__ = __str__


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
        print("Authenticating...")
        try:
            self.authenticate()
            print(self.credentials)
        except CMSAuthenticationError as e:
            print(e)
            self.credentials.remove_credentials()
            return
        print("Authenticated.")
        self.courses = self.__get_available_courses()
        print(f"Found {len(self.courses)} courses.")
        print(self.courses)

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
        return [Course(link) for link in courses_links]
