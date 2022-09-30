from scraper import *
import urllib3


def main():
    Scraper(credentials=Credentials()).run()


urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
main()
