@echo off
:: Change to your project folder
cd /d "C:\Users\gonca\Desktop\daily_eletricity_prices"

:: Optional: activate conda environment if needed
:: call "C:\Users\gonca\anaconda3\Scripts\activate.bat" base

:: (Re)install OMIEData from PyPI to ensure latest version
python -m pip install --upgrade OMIEData

:: Run your analysis script
python script.py

:: Git commands to push updates
git add .
git commit -m "Automated daily update at 22h"
git push origin main