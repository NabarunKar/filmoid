# Mood-Based Movie Recommender

Recommends movies based on user moods, using collaborative filtering techniques (SVD) trained on sampled user ratings.  
In addition, movie metadata and tag relevance information from the [MovieLens Tag Genome Dataset](https://grouplens.org/datasets/movielens/tag-genome/) is incorporated to filter recommendations based on moods.

---

## Project Structure

```
/
├── create_training_data.py       # Generate training datasets from MongoDB
├── build_model.py                # Build and train the recommendation model
├── mood_based_recommender.ipynb   # Mood-based recommendation notebook
├── data/
│   ├── training_data.csv          # Sampled user-movie-rating dataset
│   ├── review_counts.csv          # Number of reviews per movie
├── models/
│   ├── mini_model.pkl             # Trained SVD model
│   ├── threshold_movie_list.txt   # Movies with enough reviews
│   ├── user_watched.txt           # List of watched movies
└── static/
    └── data/
        └── movie_data.csv         # Movie metadata (titles, images, years)
```

---


### Generate the Datasets

```bash
python create_training_data.py
```
- Outputs:
  - `data/training_data.csv`
  - `data/review_counts.csv`
  - `static/data/movie_data.csv`
  - `models/threshold_movie_list.txt`

### Train the Recommendation Model

```bash
python build_model.py
```
- Outputs:
  - `models/mini_model.pkl`
  - `models/user_watched.txt`

### Run Mood-Based Recommender

Open and run:

```bash
mood_based_recommender.ipynb
```
- Predicts top movie recommendations based on the user’s mood and past ratings.
- Filters based on tag relevance scores from the [MovieLens Tag Genome Dataset](https://grouplens.org/datasets/movielens/tag-genome/).

---

## Main Components

### `create_training_data.py`
- Samples user ratings data from MongoDB.
- Cleans and deduplicates the ratings and movie metadata.

### `build_model.py`
- Augments existing ratings with new user inputs.
- Trains a **Singular Value Decomposition (SVD)** collaborative filtering model.
- Saves the model and the user's watched movie list.

### `mood_based_recommender.ipynb`
- Loads the saved model and user data.
- Predicts ratings for unseen movies.
- Filters recommendations based on mood using tag relevance scores.

---

## Features

- Reproducible recommendations with fixed random seeds.
- Uses tag-based mood filtering leveraging the [MovieLens Tag Genome Dataset](https://grouplens.org/datasets/movielens/tag-genome/).

