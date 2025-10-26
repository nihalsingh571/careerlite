#!/bin/bash
ls /home/careerlite
pip3 install pipenv
cd /home/peejobs
pipenv install -d
python3 /home/careerlite/manage.py migrate
python3 /home/careerlite/manage.py runserver