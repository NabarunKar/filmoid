import React, { useState } from 'react'
import { Link } from 'react-router-dom'
import './HomePage.css'

const imageUrls = [
    'public/images/video-player.png',
    'public/images/mood1.png',
    'public/images/conv2.png',
  ]
const descriptions = [
  'In the mood for a movie? Get some recommendations!',
  'Feeling something? Tell us how you feel and we\'ll suggest a movie!',
  'Wanna talk about a movie? We got you!',
]
const paths = ['/recommendations','/mood','/questions']

export default function HomePage() {
  const [selected, setSelected] = useState<number | null>(null)

  return (
    <div className="home-container">
      <h1 className="filmoid-title">Filmoid</h1>
      <table className="image-table">
        <tbody>
          <tr>
            {imageUrls.map((src, i) => (
              <td key={i}>
                <img
                  src={src}
                  alt={`Option ${i+1}`}
                  className={`table-image ${selected === i ? 'selected' : ''}`}
                  onClick={() => setSelected(i)}
                />
              </td>
            ))}
          </tr>
          <tr>
            {imageUrls.map((_, i) => (
              <td key={i} className="desc-cell">
                {selected === i && (
                  <Link to={paths[i]} className="desc-link">
                    {descriptions[i]}
                  </Link>
                )}
              </td>
            ))}
          </tr>
        </tbody>
      </table>
    </div>
  )
}
