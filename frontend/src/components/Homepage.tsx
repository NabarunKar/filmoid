import React from 'react'
import './HomePage.css'

export default function HomePage() {
    return (
      <div className="home-container">
        <h1 className="filmoid-title">Filmoid</h1>
        <div className="button-row">
          <button className="home-button">Get Recommendations</button>
          <button className="home-button">Mood‑Based Recommendations</button>
          <button className="home-button">Ask About a Movie</button>
        </div>
      </div>
    )
  }