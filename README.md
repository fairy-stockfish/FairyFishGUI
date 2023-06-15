# FairyFishGUI

[![Package exe with PyInstaller - Windows](https://github.com/fairy-stockfish/FairyFishGUI/actions/workflows/build.yml/badge.svg)](https://github.com/fairy-stockfish/FairyFishGUI/actions/workflows/build.yml)

Minimalistic generic chess variant GUI using [pyffish](https://pypi.org/project/pyffish/) and [PySimpleGUI](https://github.com/PySimpleGUI/PySimpleGUI), based on the [PySimpleGUI Chess Demo](https://github.com/PySimpleGUI/PySimpleGUI/tree/master/Chess). Supports all chess variants supported by [Fairy-Stockfish](https://github.com/fairy-stockfish/Fairy-Stockfish)/pyffish.

For well-known variants better use more polished GUIs like [LiGround](https://github.com/ml-research/liground). This project is meant as a fallback for variants where no other compatible GUI is available. Another alternative is [fairyground](https://fairyground.vercel.app/), which is less generic than this project, but can be sufficient for experimentation.

## Usage

For Windows you can download the EXE from the latest run of the [build action](https://github.com/fairy-stockfish/FairyFishGUI/actions/workflows/build.yml) (requires logging in to github). For Unix systems you can use the development setup as described below.

## Development

### Requirements

Install dependencies (e.g., in a virtualenv) using pip

    pip3 install -r requirements.txt

### Run

To start the GUI, run

    python3 fairyfishgui.py
