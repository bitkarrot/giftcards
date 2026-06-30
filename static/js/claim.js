window.PageGiftCardsClaim = {
  template: '#page-giftcards-claim',
  data() {
    return {
      claimState: 'entry',  // entry, confirm, rate_limited, loading, cards, invalid
      email: '',
      pendingCards: [],
      submitting: false
    }
  },
  mounted() {
    // Check if route has :magic_token — if so, verify the magic link
    const path = window.location.pathname
    // Match /giftcards/claim/:magic_token
    const match = path.match(/^\/giftcards\/claim\/(.+)$/)
    if (match && match[1]) {
      this.claimState = 'loading'
      this.verifyMagicLink(match[1])
    }
  },
  methods: {
    isValidEmail(val) {
      const re = /^[^\s@]+@[^\s@]+\.[^\s@]+$/
      return re.test(val)
    },

    async submitClaim() {
      if (!this.email || !this.isValidEmail(this.email)) {
        return
      }
      this.submitting = true
      try {
        const response = await fetch('/giftcards/api/v1/claim', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ email: this.email })
        })
        if (response.status === 429) {
          this.claimState = 'rate_limited'
        } else {
          // Always show confirmation (D-14 — no email enumeration)
          this.claimState = 'confirm'
        }
      } catch (error) {
        // Network error — still show confirmation to avoid revealing state
        this.claimState = 'confirm'
      } finally {
        this.submitting = false
      }
    },

    async verifyMagicLink(token) {
      try {
        const response = await fetch(`/giftcards/api/v1/claim/${token}`)
        if (response.status === 404) {
          this.claimState = 'invalid'
          return
        }
        if (!response.ok) {
          this.claimState = 'invalid'
          return
        }
        const data = await response.json()
        this.pendingCards = data.cards || []
        this.claimState = 'cards'
      } catch (error) {
        this.claimState = 'invalid'
      }
    },

    resetClaim() {
      this.claimState = 'entry'
      this.email = ''
      this.pendingCards = []
    },

    formatDate(dateString) {
      if (!dateString) return ''
      const date = new Date(dateString)
      return date.toLocaleDateString()
    }
  }
}
