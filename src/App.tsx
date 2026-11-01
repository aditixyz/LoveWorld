
import { useEffect, useRef, useState, type ChangeEvent } from 'react'
import html2canvas from 'html2canvas'
import './App.css'

const backgroundImages = [
  'https://images.unsplash.com/photo-1516589178581-6cd7833ae3b2?w=1920',
  'https://images.unsplash.com/photo-1490750967868-88aa4486c946?w=1920',
  'https://images.unsplash.com/photo-1470252649378-9c29740c9fa8?w=1920',
  'https://images.unsplash.com/photo-1511988617509-a57c8a288659?w=1920',
  'https://images.unsplash.com/photo-1518895949257-7621c3c786d7?w=1920',
]

const dailySurprises = [
  {
    title: 'You are my favourite person 💗',
    message:
      'No matter how ordinary the day is, it becomes special just because you are a part of it. Thank you for being my favourite hello and my safest place. I would choose you in every lifetime. ♡',
    image:
      'https://images.unsplash.com/photo-1516589178581-6cd7833ae3b2?w=900',
    caption: 'A little piece of our forever',
  },
  {
    title: 'A little reminder for you 🌷',
    message:
      'I hope you never forget how special you are to me. Your smile makes my day brighter, your presence makes everything better, and loving you is my favourite thing.',
    image:
      'https://images.unsplash.com/photo-1490750967868-88aa4486c946?w=900',
    caption: 'Sending you flowers and love',
  },
  {
    title: 'My happiest place is you ✨',
    message:
      'It is not about where we go or what we do. It is about being together. Even the smallest moments with you become memories I want to keep forever.',
    image:
      'https://images.unsplash.com/photo-1470252649378-9c29740c9fa8?w=900',
    caption: 'Every sunset is prettier with you',
  },
  {
    title: 'One more reason to smile ♡',
    message:
      'If I could make one wish today, it would be for us to keep making silly memories, laughing at little things, and choosing each other every single day.',
    image:
      'https://images.unsplash.com/photo-1511988617509-a57c8a288659?w=900',
    caption: 'Here is to more beautiful days',
  },
]

const memoryThemes = [
  { id: 'pink', name: 'Blush Pink' },
  { id: 'lavender', name: 'Lavender' },
  { id: 'peach', name: 'Peach' },
  { id: 'cream', name: 'Soft Cream' },
]

const galleryImages = [
  {
    src: 'https://images.unsplash.com/photo-1516589178581-6cd7833ae3b2?w=700',
    alt: 'Couple holding hands',
    className: 'gallery-tall',
  },
  {
    src: 'https://images.unsplash.com/photo-1490750967868-88aa4486c946?w=500',
    alt: 'Beautiful flowers',
    className: '',
  },
  {
    src: 'https://images.unsplash.com/photo-1511988617509-a57c8a288659?w=500',
    alt: 'Happy moments',
    className: '',
  },
  {
    src: 'https://images.unsplash.com/photo-1470252649378-9c29740c9fa8?w=700',
    alt: 'Beautiful sunset',
    className: 'gallery-wide',
  },
]

const dashboardFeatures = [
  {
    icon: '▧',
    title: 'Memories Gallery',
    description: 'All our captured moments',
    target: '#gallery',
    available: true,
  },
  {
    icon: '♡',
    title: 'Memories Timeline',
    description: 'Our story, day by day',
    target: '#memories',
    available: true,
  },
  {
    icon: '♥',
    title: 'Love Notes',
    description: 'Words from the heart',
    target: '#notes',
    available: true,
  },
  {
    icon: '🎁',
    title: 'Daily Surprises',
    description: 'A little surprise every day',
    target: '#daily-surprises',
    available: true,
  },
  {
    icon: '▦',
    title: 'Memory Studio',
    description: 'Create little keepsakes',
    target: '#memory-studio',
    available: true,
  },
  {
    icon: '♙',
    title: 'Our Profiles',
    description: 'Just the two of us',
    target: '#profiles',
    available: true,
  },
  {
    icon: '♡',
    title: 'Privacy Settings',
    description: 'Our private little world',
    target: '#privacy',
    available: false,
  },
  {
    icon: '✧',
    title: 'System Health',
    description: 'Connection status',
    target: '#system-health',
    available: false,
  },
]

function getTodaySurpriseIndex(): number {
  try {
    const today = new Date().toLocaleDateString('en-CA')
    const savedDate = localStorage.getItem('loveworld-surprise-date')
    const savedIndex = localStorage.getItem('loveworld-surprise-index')

    if (
      savedDate === today &&
      savedIndex !== null &&
      Number(savedIndex) >= 0 &&
      Number(savedIndex) < dailySurprises.length
    ) {
      return Number(savedIndex)
    }

    const newIndex = Math.floor(Math.random() * dailySurprises.length)

    localStorage.setItem('loveworld-surprise-date', today)
    localStorage.setItem('loveworld-surprise-index', String(newIndex))

    return newIndex
  } catch {
    return Math.floor(Math.random() * dailySurprises.length)
  }
}

function App() {
  const [selectedImage, setSelectedImage] = useState<string | null>(null)
  const [surpriseIndex] = useState<number>(() => getTodaySurpriseIndex())
  const [isSurpriseOpen, setIsSurpriseOpen] = useState(false)

  // Website background slideshow
  const [backgroundIndex, setBackgroundIndex] = useState(0)
  const [nextBackgroundIndex, setNextBackgroundIndex] = useState(1)
  const [showNextBackground, setShowNextBackground] = useState(false)

  const [memoryTitle, setMemoryTitle] = useState('Our Beautiful Memory')
  const [memoryDate, setMemoryDate] = useState(
    new Date().toISOString().slice(0, 10),
  )
  const [memoryCaption, setMemoryCaption] = useState(
    'Every moment with you is my favourite. ♡',
  )
  const [memoryTheme, setMemoryTheme] = useState('pink')
  const [memoryPhoto, setMemoryPhoto] = useState<string | null>(null)
  const [downloadError, setDownloadError] = useState('')

  const memoryCardRef = useRef<HTMLDivElement>(null)
  const todaySurprise = dailySurprises[surpriseIndex]

  // Background slideshow: change image every 5 seconds
  useEffect(() => {
    const interval = window.setInterval(() => {
      const nextIndex = (backgroundIndex + 1) % backgroundImages.length

      setNextBackgroundIndex(nextIndex)
      setShowNextBackground(true)

      window.setTimeout(() => {
        setBackgroundIndex(nextIndex)
        setShowNextBackground(false)
      }, 1500)
    }, 5000)

    return () => {
      window.clearInterval(interval)
    }
  }, [backgroundIndex])

  useEffect(() => {
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        setSelectedImage(null)
      }
    }

    window.addEventListener('keydown', handleKeyDown)

    return () => {
      window.removeEventListener('keydown', handleKeyDown)
    }
  }, [])

  useEffect(() => {
    return () => {
      if (memoryPhoto) {
        URL.revokeObjectURL(memoryPhoto)
      }
    }
  }, [memoryPhoto])

  const handleMemoryPhoto = (event: ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0]

    if (!file) return

    if (!file.type.startsWith('image/')) {
      setDownloadError('Please select a valid image file.')
      return
    }

    if (memoryPhoto) {
      URL.revokeObjectURL(memoryPhoto)
    }

    setMemoryPhoto(URL.createObjectURL(file))
    setDownloadError('')
  }

  const downloadMemoryCard = async () => {
    if (!memoryCardRef.current) return

    try {
      setDownloadError('')

      const canvas = await html2canvas(memoryCardRef.current, {
        scale: 2,
        useCORS: true,
        backgroundColor: null,
      })

      const link = document.createElement('a')
      link.download = 'loveworld-memory.png'
      link.href = canvas.toDataURL('image/png')
      link.click()
    } catch {
      setDownloadError('Could not download the card. Please try again.')
    }
  }

  const scrollToSection = (target: string) => {
    document.querySelector(target)?.scrollIntoView({
      behavior: 'smooth',
    })
  }

  return (
    <div className="loveworld">
      {/* Full website background slideshow */}
      <div
        className="website-background website-background-current"
        aria-hidden="true"
        style={{
          backgroundImage: `url("${backgroundImages[backgroundIndex]}")`,
        }}
      />

      <div
        className={`website-background website-background-next ${
          showNextBackground ? 'website-background-visible' : ''
        }`}
        aria-hidden="true"
        style={{
          backgroundImage: `url("${backgroundImages[nextBackgroundIndex]}")`,
        }}
      />

      <nav className="navbar">
        <a href="#home" className="logo">
          <span className="logo-heart">♥</span>
          LoveWorld
        </a>

        <div className="nav-links">
          <a href="#home" className="active">Home</a>
          <a href="#dashboard">Our World</a>
          <a href="#memories">Memories</a>
          <a href="#gallery">Gallery</a>
          <a href="#notes">Love Notes</a>
          <a href="#profiles">Profiles</a>
        </div>

        <button className="heart-button" aria-label="Our love">
          ♥
        </button>
      </nav>

      <main>
        {/* HERO SECTION */}
        <section id="home" className="hero-section">
          <div className="hero-content">
            <div className="hero-text">
              <span className="eyebrow">♡ OUR LITTLE UNIVERSE</span>

              <h1>
                Two hearts.
                <br />
                <span>One beautiful story.</span>
              </h1>

              <p>
                All our little moments, silly memories
                and favourite memories together.
              </p>

              <button
                className="explore-button"
                onClick={() => scrollToSection('#dashboard')}
              >
                Explore our world ♡
              </button>
            </div>

            <div className="hero-collage">
              <div className="photo-frame main-photo">
                <img
                  src="https://images.unsplash.com/photo-1516589178581-6cd7833ae3b2?w=700"
                  alt="Romantic couple holding hands"
                />
                <span>our favourite chapter ♡</span>
              </div>

              <div className="photo-frame small-photo">
                <img
                  src="https://images.unsplash.com/photo-1490750967868-88aa4486c946?w=400"
                  alt="Beautiful flowers"
                />
              </div>

              <div className="floating-heart">♥</div>
            </div>
          </div>
        </section>

        {/* DASHBOARD */}
        <section id="dashboard" className="dashboard-section">
          <div className="section-heading">
            <span className="eyebrow">♡ EVERYTHING IN ONE PLACE</span>
            <h2>Explore Our Little World</h2>
            <p>All the little things that make our world special.</p>
          </div>

          <div className="dashboard-grid">
            {dashboardFeatures.map((feature) => (
              <button
                key={feature.title}
                className={`dashboard-card ${
                  feature.available ? '' : 'dashboard-card-disabled'
                }`}
                disabled={!feature.available}
                onClick={() => scrollToSection(feature.target)}
              >
                <span className="dashboard-icon">{feature.icon}</span>
                <span className="dashboard-card-title">{feature.title}</span>
                <span className="dashboard-card-description">
                  {feature.description}
                </span>

                {!feature.available && (
                  <span className="coming-soon">Coming Soon</span>
                )}
              </button>
            ))}
          </div>
        </section>

        {/* DAILY SURPRISES */}
        <section id="daily-surprises" className="daily-surprise-section">
          <div className="section-heading">
            <span className="eyebrow">♡ A LITTLE SOMETHING FOR YOU</span>
            <h2>Your Daily Dose of Love</h2>
            <p>A tiny surprise, specially waiting for you today.</p>
          </div>

          <div className="surprise-container">
            {!isSurpriseOpen ? (
              <div className="surprise-closed">
                <div className="surprise-sparkle sparkle-one">✦</div>
                <div className="surprise-sparkle sparkle-two">♡</div>

                <button
                  className="surprise-envelope"
                  onClick={() => setIsSurpriseOpen(true)}
                  aria-label="Open today's surprise"
                >
                  <span className="envelope-heart">♥</span>
                  <span className="envelope-hint">Tap to open</span>
                </button>

                <h3>A little surprise is waiting...</h3>
                <p>Open your envelope and find today's love note.</p>

                <button
                  className="open-surprise-button"
                  onClick={() => setIsSurpriseOpen(true)}
                >
                  Open my surprise ♡
                </button>
              </div>
            ) : (
              <div className="surprise-reveal">
                <div className="surprise-reveal-label">
                  <span>♡ TODAY'S LITTLE SURPRISE ♡</span>
                </div>

                <div className="surprise-photo-frame">
                  <img
                    src={todaySurprise.image}
                    alt={todaySurprise.caption}
                  />
                  <span>{todaySurprise.caption}</span>
                </div>

                <h3>{todaySurprise.title}</h3>

                <p className="surprise-message">
                  {todaySurprise.message}
                </p>

                <span className="surprise-signature">
                  Made with love, just for you ♡
                </span>

                <button
                  className="close-surprise-button"
                  onClick={() => setIsSurpriseOpen(false)}
                >
                  Close surprise
                </button>
              </div>
            )}
          </div>
        </section>

        {/* MEMORY STUDIO */}
        <section id="memory-studio" className="memory-studio-section">
          <div className="section-heading">
            <span className="eyebrow">♡ MADE BY US, KEPT FOREVER</span>
            <h2>Our Memory Studio</h2>
            <p>Turn your favourite moments into little keepsakes.</p>
          </div>

          <div className="studio-layout">
            <div className="studio-editor">
              <h3>Create your memory card ♡</h3>

              <label className="studio-label" htmlFor="memory-photo">
                Choose a photo
              </label>

              <input
                id="memory-photo"
                className="studio-file-input"
                type="file"
                accept="image/*"
                onChange={handleMemoryPhoto}
              />

              <label className="studio-label" htmlFor="memory-title">
                Memory title
              </label>

              <input
                id="memory-title"
                className="studio-input"
                type="text"
                maxLength={60}
                value={memoryTitle}
                onChange={(event) => setMemoryTitle(event.target.value)}
                placeholder="Our Beautiful Memory"
              />

              <label className="studio-label" htmlFor="memory-date">
                Memory date
              </label>

              <input
                id="memory-date"
                className="studio-input"
                type="date"
                value={memoryDate}
                onChange={(event) => setMemoryDate(event.target.value)}
              />

              <label className="studio-label" htmlFor="memory-caption">
                Your caption
              </label>

              <textarea
                id="memory-caption"
                className="studio-textarea"
                maxLength={180}
                rows={3}
                value={memoryCaption}
                onChange={(event) => setMemoryCaption(event.target.value)}
                placeholder="Write something special..."
              />

              <span className="studio-label">Choose a theme</span>

              <div className="theme-options">
                {memoryThemes.map((theme) => (
                  <button
                    key={theme.id}
                    type="button"
                    className={`theme-button theme-button-${theme.id} ${
                      memoryTheme === theme.id ? 'theme-selected' : ''
                    }`}
                    onClick={() => setMemoryTheme(theme.id)}
                    aria-pressed={memoryTheme === theme.id}
                  >
                    {theme.name}
                  </button>
                ))}
              </div>

              <button
                className="download-memory-button"
                onClick={downloadMemoryCard}
              >
                Download Memory Card ↓
              </button>

              {downloadError && (
                <p className="studio-error" role="alert">
                  {downloadError}
                </p>
              )}
            </div>

            {/* LIVE PREVIEW */}
            <div className="studio-preview-area">
              <span className="preview-heading">LIVE PREVIEW ♡</span>

              <div
                ref={memoryCardRef}
                className={`memory-card-preview memory-theme-${memoryTheme}`}
              >
                <div className="preview-decoration">♡</div>

                {memoryPhoto ? (
                  <img
                    className="preview-photo"
                    src={memoryPhoto}
                    alt="Your memory"
                  />
                ) : (
                  <div className="preview-photo-placeholder">
                    <span>♡</span>
                    <p>Your favourite photo goes here</p>
                  </div>
                )}

                <div className="preview-card-content">
                  <span className="preview-card-eyebrow">
                    A LITTLE PIECE OF US
                  </span>

                  <h3>{memoryTitle || 'Our Beautiful Memory'}</h3>

                  <p className="preview-card-date">
                    {memoryDate
                      ? new Date(`${memoryDate}T00:00:00`).toLocaleDateString(
                          'en-IN',
                          {
                            day: 'numeric',
                            month: 'long',
                            year: 'numeric',
                          },
                        )
                      : 'Our special day'}
                  </p>

                  <p className="preview-card-caption">
                    {memoryCaption || 'Every moment with you is special. ♡'}
                  </p>

                  <span className="preview-card-heart">♥</span>
                  <span className="preview-card-footer">
                    FOREVER & ALWAYS
                  </span>
                </div>
              </div>

              <p className="preview-tip">
                Your card updates automatically as you edit it.
              </p>
            </div>
          </div>
        </section>

        {/* OUR PROFILES */}
        <section id="profiles" className="profiles-section">
          <div className="section-heading">
            <span className="eyebrow">♡ THE TWO HEARTS BEHIND OUR WORLD</span>
            <h2>Our Little Profiles</h2>
            <p>Two different souls, one favourite little universe.</p>
          </div>

          <div className="profiles-grid">
            <article className="profile-card">
              <div className="profile-photo-wrap">
                <img
                  className="profile-photo"
                  src="https://images.unsplash.com/photo-1534528741775-53994a69daeb?w=700&auto=format&fit=crop"
                  alt="Sample portrait for my profile"
                  loading="lazy"
                />
                <span className="profile-photo-heart">♡</span>
              </div>

              <div className="profile-details">
                <span className="profile-label">THE GIRL IN THIS STORY</span>
                <h3>Aditi</h3>
                <p className="profile-role">
                  Dreamer · Memory keeper · His favourite girl
                </p>
                <p className="profile-bio">
                  The one who saves little moments, believes in big love, and
                  makes this tiny universe feel like home.
                </p>
                <span className="profile-signature">
                  A heart full of love ♡
                </span>
              </div>
            </article>

            <article className="profile-card">
              <div className="profile-photo-wrap">
                <img
                  className="profile-photo"
                  src="https://images.unsplash.com/photo-1500648767791-00dcc994a43e?w=700&auto=format&fit=crop"
                  alt="Sample portrait for Sittu's profile"
                  loading="lazy"
                />
                <span className="profile-photo-heart">♡</span>
              </div>

              <div className="profile-details">
                <span className="profile-label">THE BOY IN THIS STORY</span>
                <h3>Sittu</h3>
                <p className="profile-role">
                  Her person · Partner in memories · Forever favourite
                </p>
                <p className="profile-bio">
                  The one who makes ordinary days feel special and is a
                  favourite part of every chapter in this story.
                </p>
                <span className="profile-signature">
                  Loved more than words ♡
                </span>
              </div>
            </article>
          </div>

          <p className="profiles-note">
            These are sample photos for now — we can replace them with your own
            pictures later. ♡
          </p>
        </section>

        {/* MEMORIES */}
        <section id="memories" className="memories-section">
          <div className="section-heading">
            <span className="eyebrow">♡ OUR MEMORY LANE</span>
            <h2>Little Moments, Forever Memories</h2>
            <p>Every picture holds a little piece of our story.</p>
          </div>

          <div className="memory-grid">
            <article className="memory-card">
              <img
                src="https://images.unsplash.com/photo-1516589178581-6cd7833ae3b2?w=600"
                alt="Couple holding hands"
              />
              <div className="memory-info">
                <span>♡ A special moment</span>
                <h3>Our Beginning</h3>
              </div>
            </article>

            <article className="memory-card">
              <img
                src="https://images.unsplash.com/photo-1490750967868-88aa4486c946?w=600"
                alt="Beautiful flowers"
              />
              <div className="memory-info">
                <span>♡ Little things</span>
                <h3>Flowers & Happiness</h3>
              </div>
            </article>

            <article className="memory-card">
              <img
                src="https://images.unsplash.com/photo-1511988617509-a57c8a288659?w=600"
                alt="Friends celebrating together"
              />
              <div className="memory-info">
                <span>♡ Forever favourite</span>
                <h3>Beautiful Days</h3>
              </div>
            </article>
          </div>
        </section>

        {/* GALLERY */}
        <section id="gallery" className="gallery-section">
          <div className="section-heading">
            <span className="eyebrow">♡ OUR LITTLE PHOTO WORLD</span>
            <h2>Captured Moments</h2>
            <p>A thousand memories, one beautiful story.</p>
          </div>

          <div className="gallery-grid">
            {galleryImages.map((photo) => (
              <div
                key={photo.src}
                className={`gallery-item ${photo.className}`}
                onClick={() => setSelectedImage(photo.src)}
                role="button"
                tabIndex={0}
                aria-label={`Open ${photo.alt}`}
                onKeyDown={(event) => {
                  if (event.key === 'Enter' || event.key === ' ') {
                    event.preventDefault()
                    setSelectedImage(photo.src)
                  }
                }}
              >
                <img src={photo.src} alt={photo.alt} />
                <span className="gallery-heart">♥</span>
              </div>
            ))}
          </div>
        </section>

        {/* LOVE NOTES */}
        <section id="notes" className="notes-section">
          <div className="section-heading">
            <span className="eyebrow">♡ WORDS FROM THE HEART</span>
            <h2>Little Love Notes</h2>
            <p>Some feelings deserve to be kept forever.</p>
          </div>

          <div className="notes-grid">
            <article className="note-card note-one">
              <span className="note-heart">♡</span>
              <p>
                In a world full of people, somehow my heart found its favourite
                person.
              </p>
              <span className="note-sign">With love, always ♡</span>
            </article>

            <article className="note-card note-two">
              <span className="note-heart">♡</span>
              <p>
                You make ordinary days feel like the most beautiful memories.
              </p>
              <span className="note-sign">A little reminder ♡</span>
            </article>

            <article className="note-card note-three">
              <span className="note-heart">♡</span>
              <p>My favourite place will always be wherever you are.</p>
              <span className="note-sign">Forever yours ♡</span>
            </article>
          </div>
        </section>

        {/* FOOTER */}
        <footer className="footer">
          <a href="#home" className="footer-logo">
            ♥ LoveWorld
          </a>

          <p>Made with endless love, just for us.</p>

          <div className="footer-links">
            <a href="#home">Home</a>
            <a href="#dashboard">Our World</a>
            <a href="#gallery">Gallery</a>
            <a href="#notes">Love Notes</a>
          </div>

          <span className="footer-heart">♡</span>
          <small>Our little universe · Forever & Always</small>
        </footer>
      </main>

      {/* IMAGE LIGHTBOX */}
      {selectedImage && (
        <div
          className="lightbox"
          onClick={() => setSelectedImage(null)}
        >
          <button
            className="lightbox-close"
            onClick={() => setSelectedImage(null)}
            aria-label="Close image"
          >
            ×
          </button>

          <img
            src={selectedImage}
            alt="Selected memory"
            onClick={(event) => event.stopPropagation()}
          />
        </div>
      )}
    </div>
  )
}

export default App
