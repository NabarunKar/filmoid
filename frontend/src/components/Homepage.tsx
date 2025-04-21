import React, { useState } from 'react'
import './HomePage.css'

// If you put images in public/images, reference by path:
const imageUrls = [
  'public/images/video-player.png',
  'public/images/mood1.png',
  'public/images/conversation.png',
]

// Or if in src/assets/images:
// import img1 from '../assets/images/img1.png'
// …then use [img1, img2, img3]

const descriptions = [
  'Description for image 1',
  'Description for image 2',
  'Description for image 3',
]

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
                {selected === i ? descriptions[i] : ''}
              </td>
            ))}
          </tr>
        </tbody>
      </table>
    </div>
  )
}