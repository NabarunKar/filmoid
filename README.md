# Movie Recommendation System

Demo video: https://www.youtube.com/watch?v=_roQRECDNK0

This repository contains the core components of a modular movie recommendation project. It supports three main features: mood-based movie recommendations, plot-based question answering, and personalized recommendations based on user ratings.

## Directory Structure

scripts/ 

├ mood_recommender.py # Recommends movies based on user mood 

├ plot_qa.py # Answers questions about movie plots 

├ past_ratings_recommender.py Recommends movies using collaborative filtering 

├ frontend/ # Contains the front-end interface code


## Features

- **Mood-Based Recommendations:** Suggests movies based on emotional context (e.g. feel-good, nostalgic, suspenseful).
- **Plot-Based Question Answering:** Allows users to ask natural language questions about movie plots.
- **Ratings-Based Recommendations:** Uses a collaborative filtering model to suggest movies based on previous user ratings.

## Folder Overview

- `scripts/`: Contains all backend logic, including data processing, model building, and recommendation algorithms.
- `frontend/`: Contains the front-end code that powers the user interface for interacting with the system.

## Getting Started

Each script can be run independently. Refer to comments within the scripts for usage guidance. Make sure necessary dependencies and data files are set up before running the code.