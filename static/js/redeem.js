window.PageGiftCardsRedeem = {
  template: '#page-giftcards-redeem',
  data() {
    return {
      giftCard: null,
      loading: true,
      tokenHash: null,
      error: false,
      copied: false,
      // 'bech32' (LNURL1...) or 'lud17' (lnurlw://...) — mirrors the
      // lnbits-qrcode-lnurl component's tab logic so both branded and
      // non-branded cards share the same toggle.
      tab: 'bech32',
      nfcTagWriting: false,
      nfcSupported: typeof NDEFReader != 'undefined'
    }
  },
  computed: {
    lnurlUrl() {
      if (!this.tokenHash) return ''
      const baseUrl = window.location.origin
      return `${baseUrl}/giftcards/api/v1/lnurl/${this.tokenHash}`
    },
    cardImageUrl() {
      if (!this.tokenHash) return ''
      const baseUrl = window.location.origin
      return `${baseUrl}/giftcards/api/v1/cards/${this.tokenHash}/image?encoding=${this.tab}`
    },
    lnurl() {
      // Compute the lightning: URI for the active tab, using the same
      // encoding logic as lnbits-qrcode-lnurl (NostrTools.nip19 for
      // bech32, scheme-swap for LUD-17).
      if (!this.lnurlUrl) return ''
      if (this.tab === 'bech32') {
        const bytes = new TextEncoder().encode(this.lnurlUrl)
        const bech32 = NostrTools.nip19.encodeBytes('lnurl', bytes)
        return `lightning:${bech32.toUpperCase()}`
      }
      // lud17: swap https:// → lnurlw://
      return this.lnurlUrl.replace('https://', 'lnurlw://')
    },
    lnurlString() {
      // Strip the scheme prefix for the text display / copy.
      if (!this.lnurl) return ''
      return this.lnurl.replace(/^(lightning|lnurlw):/i, '')
    }
  },
  async mounted() {
    await this.loadGiftCard()
    const params = new URLSearchParams(window.location.search)
    if (params.get('error') === '1') {
      this.error = true
    }
  },
  methods: {
    clearError() {
      this.error = false
    },

    async copyLnurl() {
      if (!this.lnurlString) return
      try {
        await navigator.clipboard.writeText(this.lnurlString)
        this.copied = true
        setTimeout(() => { this.copied = false }, 2000)
        this.$q.notify({ type: 'positive', message: 'LNURL copied to clipboard!' })
      } catch (e) {
        console.error('Failed to copy LNURL:', e)
        this.$q.notify({ type: 'negative', message: 'Failed to copy LNURL.' })
      }
    },

    async writeNfcTag() {
      try {
        if (!this.nfcSupported) {
          throw {
            toString: function () {
              return 'NFC not supported on this device or browser.'
            }
          }
        }
        const ndef = new NDEFReader()
        this.nfcTagWriting = true
        this.$q.notify({
          message: 'Tap your NFC tag to write the LNURL-withdraw link to it.'
        })
        await ndef.write({
          records: [{ recordType: 'url', data: this.lnurl, lang: 'en' }]
        })
        this.nfcTagWriting = false
        this.$q.notify({ type: 'positive', message: 'NFC tag written successfully.' })
      } catch (error) {
        this.nfcTagWriting = false
        this.$q.notify({
          type: 'negative',
          message: error ? error.toString() : 'An unexpected error has occurred.'
        })
      }
    },

    printCard() {
      const printWindow = window.open('', '_blank')
      printWindow.document.write(`
        <html>
          <head>
            <title>Print Gift Card</title>
            <style>
              body {
                display: flex;
                justify-content: center;
                align-items: center;
                height: 100vh;
                margin: 0;
              }
              img {
                max-width: 90%;
                max-height: 90vh;
              }
            </style>
          </head>
          <body><img src="${this.cardImageUrl}" /></body>
        </html>
      `)
      printWindow.document.close()
      printWindow.focus()
      printWindow.onload = () => {
        printWindow.print()
        printWindow.close()
      }
    },

    downloadCard() {
      const link = document.createElement('a')
      link.href = this.cardImageUrl
      link.download = `giftcard_${this.tokenHash ? this.tokenHash.slice(0, 8) : 'card'}.png`
      document.body.appendChild(link)
      link.click()
      document.body.removeChild(link)
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
      const msgBuffer = new TextEncoder().encode(message)
      const hashBuffer = await crypto.subtle.digest('SHA-256', msgBuffer)
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
