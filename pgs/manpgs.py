#!/usr/bin/python3
import cgi
import subprocess

def list_manpages():
    """Lists man pages by section number with links to individual pages."""
    print("Content-Type: text/html")
    print("")
    print("<h1>Man Pages</h1>")
    print("<ul>")
    for section in ["1", "2", "3", "4", "5", "6", "7", "8"]:
        print(f"<li><a href='/{section}'>{section} - General Commands</a></li>")
        print(f"<ul>")
        output = subprocess.check_output(["man", "--path", section])
        paths = output.decode().splitlines()
        for path in paths:
            manpage = path.split("/")[-1].replace(".gz", "")
            print(f"<li><a href='/{section}/{manpage}'>{manpage}</a></li>")
        print("</ul>")
    print("</ul>")

def generate_manpage(section, manpage):
    """Generates and returns the HTML view of a manpage."""
    output = subprocess.check_output(["man", f"{section}/{manpage}"])
    print("Content-Type: text/html")
    print("")
    print(output.decode().replace("\n", "<br>"))

form = cgi.FieldStorage()
manpage = form.getvalue("manpage")
section = form.getvalue("section")

if manpage:
    generate_manpage(section, manpage)
else:
    list_manpages()
