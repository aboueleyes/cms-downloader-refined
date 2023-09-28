import os
from typing import Optional
from getpass import getpass

from loguru import logger


class CMSAuthenticationError(Exception):
    """The CMSAuthenticationError class is raised when the user's credentials
    are invalid."""

    def __init__(self, message: Optional[str] = None) -> None:
        self.message = message
        if message is None:
            self.message = "Authentication failed."
        super().__init__(self.message)

    def __str__(self) -> str:
        return self.message


class Credentials:
    """Credentials  management."""

    def __init__(self):
        self.filename = ".env"
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
        from scraper import Scraper

        """
        Get credentials from input.
        """
        self.username = input("GUC Username: ")
        self.password = getpass(prompt="GUC Password: ")
        try:
            Scraper(credentials=self).authenticate()
            return
        except CMSAuthenticationError:
            logger.error("Authentication failed. Please try again.")
            self.__get_credentials_from_input()

    def remove_credentials(self) -> None:
        """
        Remove credentials file.
        """
        os.remove(self.filename)
        logger.info("Credentials removed.")
