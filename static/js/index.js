window.PageGiftCards = {
  template: '#page-giftcards',
  data() {
    return {
      giftCards: [],
      loading: false,
      walletBalance: 0,
      tablePagination: {
        rowsPerPage: 10
      },
      createDialog: {
        show: false,
        loading: false,
        data: {
          wallet: null,
          amount: null,
          recipient_name: '',
          sender_name: '',
          message: '',
          expires_at: null
        },
        result: null
      }
    }
  },
  computed: {
    giftCardColumns() {
      return [
        {
          name: 'amount',
          align: 'left',
          label: 'Amount',
          field: 'amount',
          sortable: true
        },
        {
          name: 'recipient_name',
          align: 'left',
          label: 'Recipient',
          field: row => row.recipient_name || 'Anonymous',
          sortable: true
        },
        {
          name: 'status',
          align: 'left',
          label: 'Status',
          field: 'status',
          sortable: true
        },
        {
          name: 'delivery',
          align: 'left',
          label: 'Delivery',
          field: row => row.email_status || 'not_sent',
          sortable: true
        },
        {
          name: 'expires_at',
          align: 'left',
          label: 'Expires',
          field: row => row.expires_at ? this.formatDate(row.expires_at) : 'Never',
          sortable: true
        }
      ]
    }
  },
  mounted() {
    this.loadGiftCards()
    this.loadWalletBalance()
  },
  methods: {
    async loadGiftCards() {
      this.loading = true
      try {
        const response = await LNbits.api.request(
          'GET',
          '/giftcards/api/v1/cards',
          this.g.user.wallets[0].adminkey
        )
        this.giftCards = response.data || []
      } catch (error) {
        LNbits.utils.notifyApiError(error)
      } finally {
        this.loading = false
      }
    },

    async loadWalletBalance() {
      try {
        if (this.g.user.wallets.length > 0) {
          const wallet = this.g.user.wallets[0]
          const response = await LNbits.api.request(
            'GET',
            '/api/v1/wallet',
            wallet.inkey
          )
          this.walletBalance = Math.floor(response.data.balance / 1000) // Convert msats to sats
        }
      } catch (error) {
        console.error('Failed to load wallet balance:', error)
      }
    },

    openCreateDialog() {
      this.createDialog.show = true
      this.resetCreateDialog()
      // Pre-select first wallet
      if (this.g.user.wallets.length > 0) {
        this.createDialog.data.wallet = this.g.user.wallets[0].id
      }
    },

    resetCreateDialog() {
      this.createDialog.data = {
        wallet: this.g.user.wallets.length > 0 ? this.g.user.wallets[0].id : null,
        amount: null,
        recipient_name: '',
        sender_name: '',
        message: '',
        expires_at: null
      }
      this.createDialog.result = null
    },

    async createGiftCard() {
      this.createDialog.loading = true
      try {
        const wallet = this.g.user.wallets.find(w => w.id === this.createDialog.data.wallet)
        const response = await LNbits.api.request(
          'POST',
          '/giftcards/api/v1/cards',
          wallet.adminkey,
          this.createDialog.data
        )
        
        this.createDialog.result = response.data
        this.loadGiftCards()
        this.loadWalletBalance() // Refresh balance
        
        LNbits.utils.notify('Gift card created successfully!', 'positive')
      } catch (error) {
        LNbits.utils.notifyApiError(error)
      } finally {
        this.createDialog.loading = false
      }
    },

    async copyLink(giftCard) {
      if (giftCard.redemption_url) {
        await this.copyToClipboard(giftCard.redemption_url)
        LNbits.utils.notify('Link copied to clipboard', 'positive')
      }
    },

    async copyToClipboard(text) {
      try {
        await navigator.clipboard.writeText(text)
      } catch (error) {
        // Fallback for older browsers
        const textArea = document.createElement('textarea')
        textArea.value = text
        document.body.appendChild(textArea)
        textArea.select()
        document.execCommand('copy')
        document.body.removeChild(textArea)
      }
    },

    formatDate(dateString) {
      if (!dateString) return ''
      const date = new Date(dateString)
      return date.toLocaleDateString()
    },

    getStatusColor(status) {
      switch (status) {
        case 'active': return 'positive'
        case 'redeemed': return 'grey-6'
        case 'expired': return 'warning'
        default: return 'grey'
      }
    },

    getStatusText(status) {
      switch (status) {
        case 'active': return 'Active'
        case 'redeemed': return 'Redeemed'
        case 'expired': return 'Expired'
        default: return status
      }
    },

    getDeliveryStatusColor(status) {
      switch (status) {
        case 'not_sent': return 'grey-6'
        case 'sent': return 'positive'
        case 'failed': return 'negative'
        default: return 'grey'
      }
    },

    getDeliveryStatusText(status) {
      switch (status) {
        case 'not_sent': return 'Not sent'
        case 'sent': return 'Sent'
        case 'failed': return 'Failed'
        default: return status
      }
    },

    async downloadPrintable(card) {
      try {
        const wallet = this.g.user.wallets.find(w => w.id === card.wallet) || this.g.user.wallets[0]
        const url = `/giftcards/api/v1/cards/${card.id}/print`
        const response = await fetch(url, {
          headers: { 'X-Api-Key': wallet.adminkey }
        })
        if (!response.ok) {
          throw new Error(`HTTP ${response.status}`)
        }
        const blob = await response.blob()
        const downloadUrl = window.URL.createObjectURL(blob)
        const a = document.createElement('a')
        a.href = downloadUrl
        a.download = `giftcard_${card.id}.png`
        document.body.appendChild(a)
        a.click()
        document.body.removeChild(a)
        window.URL.revokeObjectURL(downloadUrl)
        LNbits.utils.notify('Gift card image downloaded', 'positive')
      } catch (error) {
        LNbits.utils.notifyApiError(error)
      }
    },

    exportCSV() {
      if (this.giftCards.length === 0) {
        LNbits.utils.notify('No gift cards to export', 'warning')
        return
      }

      const headers = ['ID', 'Amount (sats)', 'Recipient', 'Sender', 'Message', 'Status', 'Created', 'Expires']
      const rows = this.giftCards.map(card => [
        card.id,
        card.amount,
        card.recipient_name || '',
        card.sender_name || '',
        card.message || '',
        card.status,
        this.formatDate(card.created_at),
        card.expires_at ? this.formatDate(card.expires_at) : 'Never'
      ])

      let csv = headers.join(',') + '\n'
      rows.forEach(row => {
        csv += row.map(cell => `"${cell}"`).join(',') + '\n'
      })

      const blob = new Blob([csv], { type: 'text/csv' })
      const url = window.URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `giftcards_${new Date().toISOString().split('T')[0]}.csv`
      a.click()
      window.URL.revokeObjectURL(url)

      LNbits.utils.notify('CSV exported successfully', 'positive')
    }
  }
}