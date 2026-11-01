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

const loveReasons = [
  'Because your smile makes my whole day better. ♡',
  'Because you make ordinary moments feel special.',
  'Because talking to you is my favourite thing.',
  'Because you understand me even when I say nothing.',
  'Because your happiness matters to me.',
  'Because you make my world brighter.',
  'Because I can be completely myself with you.',
  'Because your laugh is my favourite sound.',
  'Because you make distance feel smaller.',
  'Because every little thing reminds me of you.',
  'Because you make me feel loved.',
  'Because you are my favourite notification. 💗',
  'Because even silence feels comfortable with you.',
  'Because you make my heart feel at home.',
  'Because I love the way you care.',
  'Because you are my favourite person to annoy.',
  'Because you make bad days easier.',
  'Because I love hearing about your day.',
  'Because you make me smile without trying.',
  'Because you are my happy place.',
  'Because your presence gives me peace.',
  'Because I love your little habits.',
  'Because you make every conversation special.',
  'Because I never get tired of you.',
  'Because you are worth every effort.',
  'Because you make me feel lucky.',
  'Because I love your silly side.',
  'Because you make my heart skip a beat.',
  'Because you are beautiful inside and out.',
  'Because you make every goodbye difficult.',
  'Because I love making memories with you.',
  'Because you are my favourite thought.',
  'Because you make me feel understood.',
  'Because you bring out the best in me.',
  'Because I love your voice.',
  'Because you make me excited about tomorrow.',
  'Because you are my favourite hello.',
  'Because you make little things meaningful.',
  'Because I love your attention.',
  'Because you make my heart feel safe.',
  'Because you are cute even when you are grumpy.',
  'Because I love our random talks.',
  'Because you make me believe in love.',
  'Because you are my favourite distraction.',
  'Because I love seeing you happy.',
  'Because you make my life more colourful.',
  'Because I can share my smallest secrets with you.',
  'Because you make me feel special.',
  'Because I love your imperfectly perfect self.',
  'Because you are the person I want to tell everything.',
  'Because you make waiting worthwhile.',
  'Because I love your caring nature.',
  'Because you make my heart warm.',
  'Because you are my favourite dream.',
  'Because you make every day worth remembering.',
  'Because I love your sleepy face.',
  'Because you are my comfort person.',
  'Because you make me laugh at the weirdest things.',
  'Because I love the way you say my name.',
  'Because you make love feel effortless.',
  'Because you are my favourite adventure.',
  'Because I love your little surprises.',
  'Because you make me feel appreciated.',
  'Because I want to celebrate every little win with you.',
  'Because you make my world feel complete.',
  'Because I love your thoughtful gestures.',
  'Because you are my favourite person to miss.',
  'Because you make my heart smile.',
  'Because I love how we can be silly together.',
  'Because you make every moment count.',
  'Because you are always on my mind.',
  'Because I love your unique way of seeing things.',
  'Because you make me feel close even from far away.',
  'Because I want to keep choosing you.',
  'Because you make me look forward to little things.',
  'Because I love your kindness.',
  'Because you are my favourite story.',
  'Because you make me feel accepted.',
  'Because I love every version of you.',
  'Because you make my days sweeter.',
  'Because I love dreaming about our future.',
  'Because you are my favourite person to share food with.',
  'Because you make my heart feel full.',
  'Because I love your unexpected messages.',
  'Because you make even boring days fun.',
  'Because you are my safe corner in a busy world.',
  'Because I love being yours.',
  'Because you make me feel special without even knowing.',
  'Because I want to create a thousand more memories with you.',
  'Because you are the best part of my day.',
  'Because I love the way we are together.',
  'Because you make my world a little more magical.',
  'Because I am proud of you.',
  'Because you deserve all the happiness.',
  'Because I would still choose you in a thousand lifetimes.',
  'Because there is nobody quite like you.',
  'Because my heart picked you.',
  'Because you are my today and all my tomorrows.',
  'Because simply, you are you. ❤️',
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
    caption: 'A little piece of forever',
  },
  {
    src: 'https://images.unsplash.com/photo-1490750967868-88aa4486c946?w=500',
    alt: 'Beautiful flowers',
    className: '',
    caption: 'Flowers for my favourite person',
  },
  {
    src: 'https://images.unsplash.com/photo-1511988617509-a57c8a288659?w=500',
    alt: 'Happy moments',
    className: '',
    caption: 'The happiest little moments',
  },
  {
    src: 'https://images.unsplash.com/photo-1470252649378-9c29740c9fa8?w=700',
    alt: 'Beautiful sunset',
    className: 'gallery-wide',
    caption: 'Sunsets and sweet memories',
  },
]

const dashboardFeatures = [
  {
    icon: '✧',
    title: 'Floating Memories',
    description: 'Little moments floating around us',
    target: '#floating-memories',
    available: true,
  },
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
    icon: '🫙',
    title: 'Love Jar',
    description: 'A jar full of reasons why I love you',
    target: '#love-jar',
    available: true,
  },
  {
    icon: '💋',
    title: 'Miss Me?',
    description: 'A surprise kiss or a warm hug',
    target: '#miss-me',
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

  const [currentLoveReason, setCurrentLoveReason] = useState<number | null>(null)
  const [usedLoveReasons, setUsedLoveReasons] = useState<number[]>([])

  const [missMeType, setMissMeType] = useState<'kiss' | 'hug' | null>(null)
  const [showMissMe, setShowMissMe] = useState(false)

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

  // Love Jar: no repeat until all reasons have been shown
  const pickLoveReason = () => {
    let availableReasons = loveReasons
      .map((_, index) => index)
      .filter((index) => !usedLoveReasons.includes(index))

    if (availableReasons.length === 0) {
      availableReasons = loveReasons.map((_, index) => index)
      setUsedLoveReasons([])
    }

    const randomIndex = Math.floor(Math.random() * availableReasons.length)
    const selectedIndex = availableReasons[randomIndex]

    setCurrentLoveReason(selectedIndex)
    setUsedLoveReasons((previous) =>
      previous.includes(selectedIndex)
        ? [selectedIndex]
        : [...previous, selectedIndex],
    )
  }

  // Random kiss or hug
  const sendMissMe = () => {
    const surprise = Math.random() < 0.5 ? 'kiss' : 'hug'
    setMissMeType(surprise)
    setShowMissMe(true)
  }

  // Background slideshow
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

  // Close popups with Escape
  useEffect(() => {
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        setSelectedImage(null)
        setShowMissMe(false)
      }
    }

    window.addEventListener('keydown', handleKeyDown)

    return () => {
      window.removeEventListener('keydown', handleKeyDown)
    }
  }, [])

  // Clean up uploaded photo URL
  useEffect(() => {
    return () => {
      if (memoryPhoto) {
        URL.revokeObjectURL(memoryPhoto)
      }
    }
  }, [memoryPhoto])

  // MAGICAL TOUCH 1: Scroll reveal
  useEffect(() => {
    const reducedMotion = window.matchMedia(
      '(prefers-reduced-motion: reduce)',
    ).matches

    if (reducedMotion || !('IntersectionObserver' in window)) return

    const revealElements = document.querySelectorAll<HTMLElement>(
      [
        '.section-heading',
        '.dashboard-card',
        '.floating-memory-card',
        '.surprise-container',
        '.love-jar-container',
        '.miss-me-container',
        '.studio-layout',
        '.profile-card',
        '.memory-card',
        '.gallery-item',
        '.note-card',
      ].join(','),
    )

    revealElements.forEach((element) => {
      element.classList.add('magic-reveal')
    })

    const observer = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          if (entry.isIntersecting) {
            entry.target.classList.add('magic-visible')
            observer.unobserve(entry.target)
          }
        })
      },
      {
        threshold: 0.12,
        rootMargin: '0px 0px -35px 0px',
      },
    )

    revealElements.forEach((element) => observer.observe(element))

    return () => observer.disconnect()
  }, [])

  // MAGICAL TOUCH 2: Tiny floating hearts on button/link clicks
  useEffect(() => {
    const reducedMotion = window.matchMedia(
      '(prefers-reduced-motion: reduce)',
    ).matches

    if (reducedMotion) return

    const handleMagicClick = (event: MouseEvent) => {
      const target = event.target as HTMLElement
      const clickable = target.closest('button, a')

      if (!clickable || clickable.hasAttribute('disabled')) return
      if (clickable.classList.contains('miss-me-close')) return
      if (clickable.classList.contains('lightbox-close')) return

      const symbols = ['♡', '♥', '✦', '✨']
      const colors = ['#ed79a8', '#d94f88', '#c18acb', '#f2b6c9']

      for (let i = 0; i < 5; i++) {
        const particle = document.createElement('span')
        particle.className = 'magic-click-particle'
        particle.textContent = symbols[Math.floor(Math.random() * symbols.length)]

        const angle = (Math.PI * 2 * i) / 5
        const distance = 35 + Math.random() * 45

        particle.style.left = `${event.clientX}px`
        particle.style.top = `${event.clientY}px`
        particle.style.setProperty('--magic-x', `${Math.cos(angle) * distance}px`)
        particle.style.setProperty('--magic-y', `${Math.sin(angle) * distance}px`)
        particle.style.color = colors[Math.floor(Math.random() * colors.length)]

        document.body.appendChild(particle)

        window.setTimeout(() => {
          particle.remove()
        }, 850)
      }
    }

    document.addEventListener('click', handleMagicClick)

    return () => {
      document.removeEventListener('click', handleMagicClick)
    }
  }, [])

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
      <style>{`
        /* MISS ME FEATURE */
        .miss-me-section {
          padding: 90px 7%;
          text-align: center;
        }

        .miss-me-container {
          position: relative;
          max-width: 520px;
          margin: 35px auto 0;
          padding: 45px 25px;
          border: 1px solid rgba(255,255,255,.65);
          border-radius: 28px;
          background: rgba(255,245,249,.82);
          box-shadow: 0 15px 45px rgba(120,50,80,.12);
          backdrop-filter: blur(12px);
        }

        .miss-me-heart {
          font-size: 65px;
          color: #e65b91;
          animation: missMeHeartbeat 1.5s infinite;
        }

        .miss-me-container h3 {
          margin: 15px 0 8px;
          color: #803b5b;
          font-size: 25px;
        }

        .miss-me-container p {
          color: #80596a;
          margin-bottom: 25px;
        }

        .miss-me-button,
        .miss-me-again {
          border: none;
          border-radius: 50px;
          padding: 14px 30px;
          background: linear-gradient(135deg,#ed79a8,#d94f88);
          color: white;
          font-size: 16px;
          font-weight: 600;
          cursor: pointer;
          box-shadow: 0 8px 20px rgba(217,79,136,.25);
          transition: transform .25s,box-shadow .25s;
        }

        .miss-me-button:hover,
        .miss-me-again:hover {
          transform: translateY(-3px) scale(1.04);
          box-shadow: 0 12px 25px rgba(217,79,136,.35);
        }

        .miss-me-caption {
          display: block;
          margin-top: 22px;
          color: #a16d83;
          font-size: 13px;
        }

        .miss-me-overlay {
          position: fixed;
          inset: 0;
          z-index: 10000;
          display: flex;
          align-items: center;
          justify-content: center;
          padding: 20px;
          background: rgba(48,20,35,.65);
          backdrop-filter: blur(8px);
          animation: missMeFadeIn .25s ease;
        }

        .miss-me-popup {
          position: relative;
          width: 100%;
          max-width: 420px;
          padding: 45px 25px 35px;
          border: 1px solid rgba(255,255,255,.8);
          border-radius: 30px;
          background: linear-gradient(145deg,#fff2f7,#ffe1ec);
          text-align: center;
          box-shadow: 0 20px 70px rgba(0,0,0,.25);
          animation: missMePop .45s cubic-bezier(.2,1.4,.5,1);
        }

        .miss-me-close {
          position: absolute;
          top: 12px;
          right: 17px;
          border: none;
          background: transparent;
          color: #9a5572;
          font-size: 30px;
          cursor: pointer;
        }

        .miss-me-animation {
          font-size: 100px;
          line-height: 1.3;
          animation: missMeBounce .8s ease-in-out infinite alternate;
        }

        .miss-me-popup h3 {
          margin: 15px 0 8px;
          color: #a63d6b;
          font-size: 25px;
        }

        .miss-me-popup p {
          margin-bottom: 25px;
          color: #89536b;
          font-size: 17px;
        }

        @keyframes missMeHeartbeat {
          0%,100% { transform: scale(1); }
          50% { transform: scale(1.15); }
        }

        @keyframes missMeFadeIn {
          from { opacity: 0; }
          to { opacity: 1; }
        }

        @keyframes missMePop {
          from { opacity: 0; transform: scale(.65); }
          to { opacity: 1; transform: scale(1); }
        }

        @keyframes missMeBounce {
          from { transform: translateY(0) rotate(-8deg); }
          to { transform: translateY(-12px) rotate(8deg); }
        }

        @media (max-width:600px) {
          .miss-me-section { padding: 65px 5%; }
          .miss-me-container { padding: 35px 18px; }
          .miss-me-popup h3 { font-size: 22px; }
        }

        /* MAGICAL TOUCH 3: SCROLL REVEAL */
        .magic-reveal {
          opacity: 0;
          transform: translateY(28px);
          transition:
            opacity .75s ease,
            transform .75s cubic-bezier(.2,.7,.2,1);
        }

        .magic-reveal.magic-visible {
          opacity: 1;
          transform: translateY(0);
        }

        /* MAGICAL TOUCH 4: DASHBOARD HOVER */
        .dashboard-card {
          transition:
            transform .35s ease,
            box-shadow .35s ease,
            border-color .35s ease;
          overflow: hidden;
        }

        .dashboard-card:not(:disabled):hover {
          transform: translateY(-9px) scale(1.025);
          box-shadow:
            0 18px 38px rgba(195, 91, 137, .2),
            0 0 18px rgba(255, 190, 220, .35);
          border-color: rgba(230, 120, 165, .55);
        }

        .dashboard-card:not(:disabled):hover .dashboard-icon {
          display: inline-block;
          animation: magicIconBounce .55s ease;
        }

        @keyframes magicIconBounce {
          0%,100% { transform: translateY(0) scale(1); }
          35% { transform: translateY(-7px) scale(1.16); }
          65% { transform: translateY(2px) scale(.96); }
        }

        /* MAGICAL TOUCH 5: GALLERY ZOOM */
        .gallery-item {
          overflow: hidden;
        }

        .gallery-item img,
        .floating-memory-card img,
        .memory-card img,
        .profile-photo {
          transition: transform .65s cubic-bezier(.2,.7,.2,1);
        }

        .gallery-item:hover img {
          transform: scale(1.09);
        }

        .floating-memory-card:hover img {
          transform: scale(1.06) rotate(1deg);
        }

        /* MAGICAL TOUCH 6: CARD LIFT */
        .memory-card,
        .profile-card,
        .note-card,
        .floating-memory-card {
          transition:
            transform .35s ease,
            box-shadow .35s ease;
        }

        .memory-card:hover,
        .profile-card:hover,
        .note-card:hover {
          transform: translateY(-8px);
          box-shadow: 0 18px 40px rgba(120, 50, 80, .16);
        }

        .floating-memory-card:hover {
          transform: translateY(-8px) rotate(0deg) scale(1.025);
          box-shadow: 0 18px 38px rgba(120, 50, 80, .2);
        }

        /* MAGICAL TOUCH 7: HEADING SHIMMER */
        .section-heading h2 {
          background: linear-gradient(
            110deg,
            #80435f 20%,
            #d76f9c 40%,
            #f2b4ce 50%,
            #d76f9c 60%,
            #80435f 80%
          );
          background-size: 220% auto;
          background-clip: text;
          -webkit-background-clip: text;
          -webkit-text-fill-color: transparent;
          animation: magicHeadingShimmer 6s linear infinite;
        }

        @keyframes magicHeadingShimmer {
          to { background-position: 220% center; }
        }

        /* MAGICAL TOUCH 8: FLOATING CLICK HEARTS */
        .magic-click-particle {
          position: fixed;
          z-index: 20000;
          pointer-events: none;
          font-size: 17px;
          line-height: 1;
          animation: magicParticleFloat .85s ease-out forwards;
          text-shadow: 0 2px 8px rgba(220, 90, 145, .2);
        }

        @keyframes magicParticleFloat {
          0% {
            opacity: 0;
            transform: translate(-50%, -50%) scale(.3) rotate(-20deg);
          }
          20% {
            opacity: 1;
            transform: translate(-50%, -50%) scale(1.2) rotate(10deg);
          }
          100% {
            opacity: 0;
            transform:
              translate(
                calc(-50% + var(--magic-x)),
                calc(-50% + var(--magic-y))
              )
              scale(.5)
              rotate(35deg);
          }
        }

        /* Smooth section navigation */
        html {
          scroll-behavior: smooth;
        }

        /* ACCESSIBILITY: RESPECT REDUCED MOTION */
        @media (prefers-reduced-motion: reduce) {
          *,
          *::before,
          *::after {
            scroll-behavior: auto !important;
            animation-duration: .01ms !important;
            animation-iteration-count: 1 !important;
            transition-duration: .01ms !important;
          }

          .magic-reveal {
            opacity: 1;
            transform: none;
          }
        }
      `}</style>

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

        {/* FLOATING MEMORIES */}
        <section id="floating-memories" className="floating-memories-section">
          <div className="section-heading">
            <span className="eyebrow">♡ LITTLE MOMENTS, BIG FEELINGS</span>
            <h2>Our Memories in the Air</h2>
            <p>Some moments are too special to stay in one place. ♡</p>
          </div>

          <div className="floating-memories-grid">
            {galleryImages.map((photo, index) => (
              <button
                key={photo.src}
                type="button"
                className={`floating-memory-card floating-memory-${index + 1}`}
                onClick={() => setSelectedImage(photo.src)}
                aria-label={`Open memory: ${photo.caption}`}
              >
                <span className="floating-memory-pin">♡</span>
                <img src={photo.src} alt={photo.alt} loading="lazy" />
                <span className="floating-memory-caption">
                  {photo.caption}
                </span>
              </button>
            ))}
          </div>

          <p className="floating-memories-hint">
            Tap any little picture to see it up close ✨
          </p>
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

        {/* LOVE JAR */}
        <section id="love-jar" className="love-jar-section">
          <div className="section-heading">
            <span className="eyebrow">♡ A JAR FULL OF LOVE</span>
            <h2>100 Little Reasons I Love You</h2>
            <p>
              Whenever you need a little reminder, pick a reason from my heart. ♡
            </p>
          </div>

          <div className="love-jar-container">
            <div className="love-jar-decoration jar-decoration-one">✦</div>
            <div className="love-jar-decoration jar-decoration-two">♡</div>

            <div className="love-jar">
              <div className="jar-lid">
                <div className="jar-lid-top" />
              </div>

              <div className="jar-neck" />

              <div className="jar-glass">
                <div className="jar-shine" />

                <div className="jar-notes">
                  {Array.from({ length: 12 }).map((_, index) => (
                    <span
                      key={index}
                      className={`jar-paper jar-paper-${(index % 4) + 1}`}
                    >
                      ♡
                    </span>
                  ))}
                </div>

                <span className="jar-front-heart">♥</span>
                <span className="jar-front-label">LOVE</span>
                <span className="jar-front-small">A LITTLE EVERY DAY</span>
              </div>
            </div>

            <p className="jar-caption">
              A hundred feelings, tucked into little notes. 💌
            </p>

            {currentLoveReason === null ? (
              <div className="love-jar-message">
                <h3>A little love is waiting inside...</h3>
                <p>
                  Pick a tiny note and let me remind you how special you are.
                </p>
              </div>
            ) : (
              <div className="love-reason-card" key={currentLoveReason}>
                <span className="love-reason-heart">♡</span>
                <span className="love-reason-label">
                  A REASON FROM MY HEART
                </span>
                <p>{loveReasons[currentLoveReason]}</p>
                <span className="love-reason-signature">
                  Always yours ♡
                </span>
              </div>
            )}

            <button className="pick-love-button" onClick={pickLoveReason}>
              {currentLoveReason === null
                ? 'Pick a little love ♡'
                : 'Pick another note ♡'}
            </button>

            <span className="jar-counter">
              {usedLoveReasons.length} of {loveReasons.length} little reasons
              discovered
            </span>
          </div>
        </section>

        {/* MISS ME */}
        <section id="miss-me" className="miss-me-section">
          <div className="section-heading">
            <span className="eyebrow">♡ A LITTLE SURPRISE FOR YOU</span>
            <h2>Miss Me? 💗</h2>
            <p>
              Missing me? Tap the button and collect your little surprise.
            </p>
          </div>

          <div className="miss-me-container">
            <div className="miss-me-heart">♡</div>

            <h3>A little love is waiting for you!</h3>
            <p>Tap below to get a surprise.</p>

            <button className="miss-me-button" onClick={sendMissMe}>
              Miss Me? 💗
            </button>

            <span className="miss-me-caption">
              A kiss or a hug, straight from my heart ♡
            </span>
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

      {/* MISS ME POPUP */}
      {showMissMe && missMeType && (
        <div
          className="miss-me-overlay"
          onClick={() => setShowMissMe(false)}
        >
          <div
            className="miss-me-popup"
            onClick={(event) => event.stopPropagation()}
          >
            <button
              className="miss-me-close"
              onClick={() => setShowMissMe(false)}
              aria-label="Close surprise"
            >
              ×
            </button>

            <div className="miss-me-animation" key={missMeType}>
              {missMeType === 'kiss' ? '💋' : '🤗'}
            </div>

            <h3>
              {missMeType === 'kiss'
                ? 'A Sweet Kiss for You!'
                : 'A Warm Hug for You!'}
            </h3>

            <p>
              {missMeType === 'kiss'
                ? 'Muaahhh! 💋'
                : 'Come here, tight hug! 🤗'}
            </p>

            <button className="miss-me-again" onClick={sendMissMe}>
              One More Surprise ♡
            </button>
          </div>
        </div>
      )}

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