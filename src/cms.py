import requests
from bs4 import BeautifulSoup
import json
from typing import Tuple, List, Type, Optional, Dict
import os
from requests_ntlm import HttpNtlmAuth
import re
from getpass import getpass
import yaml
import random
from datetime import datetime
from contextlib import suppress
from sanitize_filename import sanitize
from tqdm import tqdm

YML_FILE = "config.yml"
YML_CONFIG = yaml.safe_load(open(YML_FILE))
HOST = YML_CONFIG["host"]+"apps/student/ViewAllCourseStn"
print(HOST)
DOWNLOADS_DIR = YML_CONFIG["downloads_dir"]
COLORS = ["#ff0000", "#00ff00", "#0000ff", "#ffff00",
          "#00ffff", "#ff00ff", "#ffffff", "#000000"]


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

    def __init__(self, course_url: str, fer: "Scraper") -> None:
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
        self.course_name = course_text.split(" ")[0].strip()

    def create_course_directory(self) -> None:
        for file in self.files:
            os.makedirs(os.path.join(file.dir_path), exist_ok=True)

    def set_course_soup(self, course_soup: BeautifulSoup) -> None:
        self.course_soup = course_soup

    def get_course_files(self, course_path) -> List[str]:
        """
        Get the list of files in the course.
        """
        files_body = self.course_soup.find_all(class_="card-body")

        for item in files_body:
            self.files.append((CMSFile(soup=item, course_path=course_path)))


class CMSFile:
    """ a cms file object"""

    def __init__(self, soup: BeautifulSoup, course_path) -> None:
        self.soup = soup
        self.url = HOST + self.soup.find("a")["href"]
        self.week = self.soup.parent.parent.parent.parent.find(
            "h2").text.strip()
        self.week = re.sub(r"Week: (.*)", "\\1", self.week)
        self.week = datetime.strptime(self.week, '%Y-%m-%d').strftime('W %m-%d')
        self.description = re.sub(self.get_file_regex(
        ), '\\1', self.soup.find('div').text).strip()
        self.name = re.sub(self.get_file_regex(), '\\1',
                           self.soup.find('strong').text).strip()
        self.name = sanitize(self.name)
        self.extension = self.url.rsplit(".", 1)[1]
        self.dir_path = os.path.join(course_path, self.week)
        self.path = os.path.join(
            self.dir_path, f"{self.name}.{self.extension}")

    @staticmethod
    def get_file_regex() -> re.Pattern:
        return re.compile(r'[0-9]* - (.*)')

    def __str__(self) -> str:
        return f"{self.name}"

    __repr__ = __str__


def exists(self) -> bool:
    return os.path.exists(self.path)


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

        try:
            file = open("courses.json")
            courses_data = json.load(file)
            courses_names = []
            for course in courses_data:
                courses_names.append(course)
            self.course_names = courses_names

            links = []
            for link in courses_data.values():
                links.append(link)
            self.courses = [Course(links[i], self) for i in range(len(links))]

        except FileNotFoundError:
            print("file not found")
            self.course_names = self.__get_course_names()
            courses_links = self.__get_courses_links()
            self.courses = [Course(courses_links[i], self) for i in range(len(courses_links))]

            print(self.course_names)
            courses_data = {}
            for course_name in self.course_names:
                for link in courses_links:
                    courses_data[course_name] = link
                    courses_links.remove(link)
                    break

            with open("courses.json", "w") as outfile:
                json.dump(courses_data, outfile)

        for course, course_name in zip(self.courses, self.course_names):
            course.set_course_code(course_name)
            course.set_course_name(course_name)

        self.get_courses_soup()

        for course in self.courses:
            course.get_course_files(os.path.join(
                DOWNLOADS_DIR, course.__str__()))

        for course in self.courses:
            course.create_course_directory()

        print(self.courses)
        first_file = self.courses[0].files[0]
        self.__download_file(first_file)

    def authenticate(self) -> None:
        """
        Authenticate with GUC CMS.
        """
        response = self.session.get(HOST, **self.get_args)
        if response.status_code != 200:
            raise CMSAuthenticationError("Authentication failed.")

    #def __get_available_courses(self) -> Type[List[Course]]:
        #"""
        #Get list of courses.
        #"""
        #return [Course(courses_links[i], self.courses_names[i]) for i in range(len(courses_links))]
    
    def __get_courses_links(self) -> List[str]:
        """
        Get list of courses links.
        """
        courses_codes=[]
        for str in self.course_names:
            course_code=re.findall(r'\([0-9]*\)',str)[0]
            course_code=course_code[1:len(course_code)-1]
            courses_codes.append(course_code)
        print(courses_codes)
        season=self.home_soup.find("div",{"class": "menu-header-title"}).get_text()[9:11]
        print(season)
        courses_links = []
        for code in courses_codes:
            courses_links.append("https://cms.guc.edu.eg/apps/student/CourseViewStn.aspx?id="+code+"&sid="+ season)
        
        return courses_links

    def __get_course_names(self) -> List[str]:
        "get course names"
        #courses_table = list(
            #self.home_soup.find(
                #"table",
                #{
                    #"id": "ContentPlaceHolderright_ContentPlaceHoldercontent_r1_GridView1_0"
                #}
            #)
        #)
        #return [
            #re.sub(
                #Course.get_course_regex(),
                #r"\1-\2",
                #courses_table[i].text.strip(),
            #).strip()
            #for i in range(2, len(courses_table) - 1)
        #]
        search_area = self.home_soup.find("table",{"id": "ContentPlaceHolderright_ContentPlaceHoldercontent_r1_GridView1_0"})
        courses_names = [ str(name)[4:len(str(name))-5] for name in search_area.find_all("td") if (len(name)==1 and str(name)[4]=='(')]
        #print(len(courses_names))
        #print(courses_names)
        return courses_names

    def get_courses_soup(self) -> None:
        """
        Get courses page.
        """
        for course in self.courses:
            course.set_course_soup(BeautifulSoup(
                self.session.get(course.course_url, **
                                 self.get_args).text, self.html_parser
            ))

    def __download_file(self, file: CMSFile) -> None:
        response = self.session.get(
            file.url, **self.get_args, stream=True, allow_redirects=True)
        if response.status_code != 200:
            raise CMSAuthenticationError("Authentication failed.")

        total_size = int(response.headers.get("Content-Length"))

        with open(file.path, "wb") as f:
            with tqdm(
                total=total_size,
                unit='B',
                unit_scale=True,
                desc=file.path,
                initial=0,
                dynamic_ncols=True,
                colour=random.choice(COLORS),
            ) as t:
                for chunk in response.iter_content(chunk_size=1024):
                    f.write(chunk)
                    t.update(len(chunk))
