window.PageGiftCardsRedeem = {
  template: '#page-giftcards-redeem',
  data() {
    return {
      giftCard: null,
      loading: true,
      tokenHash: null,
      error: false
    }
  },
  computed: {
    qrCodeUrl() {
      if (!this.tokenHash) return ''
      const baseUrl = window.location.origin
      return `${baseUrl}/giftcards/api/v1/lnurl/${this.tokenHash}/qr`
    },
    lightningUri() {
      if (!this.tokenHash) return ''
      const baseUrl = window.location.origin
      const lnurl = `${baseUrl}/giftcards/api/v1/lnurl/${this.tokenHash}`
      // Note: In a real implementation, you might want to encode this as bech32
      // For now, we'll just return the HTTPS URL
      return null // Disable lightning: URI for Phase 1 as per UI spec
    },
    qrSize() {
      return this.$q.screen.lt.md ? 240 : 300
    }
  },
  async mounted() {
    await this.loadGiftCard()
    // A wallet that fails the LNURL callback may return the user to this page
    // with ?error=1. Show the error state without reloading the page.
    const params = new URLSearchParams(window.location.search)
    if (params.get('error') === '1') {
      this.error = true
    }
  },
  methods: {
    clearError() {
      this.error = false
    },

    async loadGiftCard() {
      this.loading = true
      try {
        // Get raw token from URL path
        const pathParts = window.location.pathname.split('/')
        const rawToken = pathParts[pathParts.length - 1]
        
        if (!rawToken || rawToken === 'redeem') {
          this.giftCard = null
          return
        }

        // Compute SHA-256 hash in the browser
        this.tokenHash = await this.computeSHA256(rawToken)
        
        // Load public card data
        const response = await fetch(
          `/giftcards/api/v1/cards/public/${this.tokenHash}`
        )
        
        if (response.ok) {
          this.giftCard = await response.json()
        } else {
          this.giftCard = null
        }
      } catch (error) {
        console.error('Failed to load gift card:', error)
        this.giftCard = null
      } finally {
        this.loading = false
      }
    },

    async computeSHA256(message) {
      // Encode message as UTF-8
      const msgBuffer = new TextEncoder().encode(message)
      
      // Hash the message
      const hashBuffer = await crypto.subtle.digest('SHA-256', msgBuffer)
      
      // Convert ArrayBuffer to hex string
      const hashArray = Array.from(new Uint8Array(hashBuffer))
      const hashHex = hashArray.map(b => b.toString(16).padStart(2, '0')).join('')
      
      return hashHex
    },

    formatDate(dateString) {
      if (!dateString) return ''
      const date = new Date(dateString)
      return date.toLocaleDateString()
    }
  }
}