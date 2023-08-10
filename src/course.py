import os
import re
from datetime import datetime

from bs4 import BeautifulSoup
from sanitize_filename import sanitize


class Course:
    """
    Class for storing course information.
    """

    def __init__(self, course_url: str) -> None:
        self.course_url = course_url
        self.id = self.course_url.split("id")[1][1:].split("&")[0]
        self.files = []

    def __str__(self) -> str:
        return f"[{self.course_code}] {self.course_name}"

    __repr__ = __str__

    @staticmethod
    def get_course_regex() -> re.Pattern:
        return re.compile(r"\n*[\(][\|]([^\|]*)[\|][\)]([^\(]*)[\(].*\n*")

    @property
    def course_code(self) -> None:
        return self.course_text.split("-")[0].strip()

    @property
    def course_name(self) -> None:
        return self.course_text.split("-")[1].strip()

    def set_course_text(self, course_text: str) -> None:
        """
        Set the course text. (e.g. "CS 201 - Programming 1")
        course code + course name

        :param course_text: The course text.
        """
        self.course_text = course_text

    def create_course_directory(self) -> None:
        for file in self.files:
            os.makedirs(os.path.join(file.dir_path), exist_ok=True)

    def set_course_soup(self, course_soup: BeautifulSoup) -> None:
        self.course_soup = course_soup

    def get_course_files(self, course_path) -> None:
        """
        Get the list of files in the course.
        """
        files_body = self.course_soup.find_all(class_="card-body")

        for item in files_body:
            # check if the card is not a course content, useful for `Filter weeks` card
            if item.find('strong') is None:
                continue
            self.files.append((CMSFile(soup=item, course_path=course_path)))


class CMSFile:
    """a cms file object"""

    def __init__(self, soup: BeautifulSoup, course_path) -> None:
        from scraper import HOST

        self.soup = soup

        self.url = HOST + self.soup.find("a")["href"]

        self.week = self.soup.parent.parent.parent.parent.find("h2").text.strip()
        self.week = re.sub(r"Week: (.*)", "\\1", self.week)
        self.week = datetime.strptime(self.week, "%Y-%m-%d").strftime("W %m-%d")

        self.description = re.sub(self.get_file_regex(), "\\1", self.soup.find("div").text).strip()

        self.name = re.sub(self.get_file_regex(), "\\1", self.soup.find("strong").text).strip()
        self.name = sanitize(self.name)

        self.extension = self.url.rsplit(".", 1)[1]
        self.dir_path = os.path.join(course_path, self.week)
        self.path = os.path.join(self.dir_path, f"{self.name}.{self.extension}")

    @staticmethod
    def get_file_regex() -> re.Pattern:
        return re.compile(r"[0-9]* - (.*)")

    def __str__(self) -> str:
        return f"{self.name}"

    __repr__ = __str__