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
      },
      // Card designer state
      selectedTemplate: 'portrait',
      templateAssetId: null,
      templateUrl: '/giftcards/static/image/template_portrait.png',
      qrX: 21,
      qrY: 228,
      qrSize: 150,
      textX: 21,
      textY: 33,
      selectedFont: 'DejaVuSans',
      fontSize: 24,
      fontColor: '#000000',
      textAlign: 'left',
      showAmount: true,
      showRecipient: true,
      showMessage: true,
      previewWidth: 212,
      previewHeight: 325,
      minQrSize: 150,
      dragState: null,
      resizeState: null,
      isUploadingTemplate: false,
      // Email delivery dialog
      emailDialog: {
        show: false,
        loading: false,
        card: null,
        data: {
          recipient_email: '',
          email_mode: 'custom',
          subject: '',
          body: '',
          template: 'notification'
        }
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
    },
    templateOptions() {
      return [
        {label: 'Portrait (425x650)', value: 'portrait'},
        {label: 'Landscape (1050x600)', value: 'landscape'},
        {label: 'Custom Upload', value: 'custom'}
      ]
    },
    fontOptions() {
      return [
        {label: 'DejaVu Sans', value: 'DejaVuSans'},
        {label: 'DejaVu Serif', value: 'DejaVuSerif'},
        {label: 'DejaVu Sans Mono', value: 'DejaVuSansMono'}
      ]
    },
    anyTextShown() {
      return this.showAmount || this.showRecipient || this.showMessage
    },
    emailModeOptions() {
      return [
        {label: 'Custom Text', value: 'custom'},
        {label: 'Fancy HTML Template', value: 'fancy'}
      ]
    },
    previewTextStyle() {
      const alignMap = {
        left: 'left',
        center: 'center',
        right: 'right'
      }
      const fontFamilyMap = {
        DejaVuSans: 'sans-serif',
        DejaVuSerif: 'serif',
        DejaVuSansMono: 'monospace'
      }
      return {
        fontFamily: fontFamilyMap[this.selectedFont] || 'sans-serif',
        fontSize: this.fontSize + 'px',
        color: this.fontColor,
        textAlign: alignMap[this.textAlign] || 'left',
        lineHeight: '1.3'
      }
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
      // Reset card designer to defaults
      this.selectedTemplate = 'portrait'
      this.templateAssetId = null
      this.templateUrl = '/giftcards/static/image/template_portrait.png'
      this.qrX = 21
      this.qrY = 228
      this.qrSize = 150
      this.textX = 21
      this.textY = 33
      this.selectedFont = 'DejaVuSans'
      this.fontSize = 24
      this.fontColor = '#000000'
      this.textAlign = 'left'
      this.showAmount = true
      this.showRecipient = true
      this.showMessage = true
      this.previewWidth = 212
      this.previewHeight = 325
      this.dragState = null
      this.resizeState = null
    },

    async createGiftCard() {
      this.createDialog.loading = true
      try {
        const wallet = this.g.user.wallets.find(w => w.id === this.createDialog.data.wallet)
        // Build design config with normalized fractions
        const designConfig = {
          template_asset_id: this.templateAssetId,
          template_name: this.selectedTemplate,
          qr_x_frac: this.qrX / this.previewWidth,
          qr_y_frac: this.qrY / this.previewHeight,
          qr_size: this.qrSize,
          text_x_frac: this.textX / this.previewWidth,
          text_y_frac: this.textY / this.previewHeight,
          font_family: this.selectedFont,
          font_size: this.fontSize,
          font_color: this.fontColor,
          text_align: this.textAlign,
          show_amount: this.showAmount,
          show_recipient: this.showRecipient,
          show_message: this.showMessage
        }
        const payload = {
          ...this.createDialog.data,
          design: designConfig
        }
        const response = await LNbits.api.request(
          'POST',
          '/giftcards/api/v1/cards',
          wallet.adminkey,
          payload
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
    },

    // ----- Card Designer: drag interaction -----

    startDrag(event, target) {
      event.preventDefault()
      this.dragState = {
        target: target,
        startX: event.clientX,
        startY: event.clientY,
        origX: target === 'qr' ? this.qrX : this.textX,
        origY: target === 'qr' ? this.qrY : this.textY
      }
      event.target.setPointerCapture(event.pointerId)
    },

    onDrag(event) {
      if (!this.dragState) return
      const dx = event.clientX - this.dragState.startX
      const dy = event.clientY - this.dragState.startY
      const newX = this.dragState.origX + dx
      const newY = this.dragState.origY + dy
      if (this.dragState.target === 'qr') {
        this.qrX = Math.max(0, Math.min(newX, this.previewWidth - this.qrSize))
        this.qrY = Math.max(0, Math.min(newY, this.previewHeight - this.qrSize))
      } else {
        this.textX = Math.max(0, Math.min(newX, this.previewWidth))
        this.textY = Math.max(0, Math.min(newY, this.previewHeight))
      }
    },

    endDrag() {
      this.dragState = null
    },

    // ----- Card Designer: QR resize -----

    startResize(event) {
      event.preventDefault()
      this.resizeState = {
        startX: event.clientX,
        origSize: this.qrSize
      }
      event.target.setPointerCapture(event.pointerId)
    },

    onResize(event) {
      if (!this.resizeState) return
      const dx = event.clientX - this.resizeState.startX
      const newSize = Math.max(this.minQrSize, this.resizeState.origSize + dx)
      this.qrSize = Math.min(newSize, this.previewWidth - this.qrX)
    },

    endResize() {
      this.resizeState = null
    },

    // ----- Card Designer: template selection & upload -----

    onTemplateChange(value) {
      if (value === 'portrait') {
        this.previewWidth = 212
        this.previewHeight = 325
        this.templateUrl = '/giftcards/static/image/template_portrait.png'
        this.templateAssetId = null
      } else if (value === 'landscape') {
        this.previewWidth = 262
        this.previewHeight = 150
        this.templateUrl = '/giftcards/static/image/template_landscape.png'
        this.templateAssetId = null
      }
      // 'custom' — preview set after upload
    },

    triggerTemplateUpload() {
      this.$refs.templateUpload.value = null
      this.$refs.templateUpload.click()
    },

    async handleTemplateSelected(event) {
      const file = event.target.files && event.target.files[0]
      if (!file) return

      // D-03: validate image dimensions (max 1500x2000px) client-side
      try {
        const dims = await this._getImageDimensions(file)
        if (dims.width > 1500 || dims.height > 2000) {
          LNbits.utils.notify(
            'Template image too large. Maximum dimensions are 1500x2000px.',
            'negative'
          )
          return
        }
      } catch (err) {
        LNbits.utils.notify('Could not read image file.', 'negative')
        return
      }

      this.isUploadingTemplate = true
      try {
        const assetId = await this.uploadAssetFile(file)
        this.templateAssetId = assetId
        this.templateUrl = `/api/v1/assets/${assetId}/data`
        LNbits.utils.notify('Custom template uploaded', 'positive')
      } catch (error) {
        LNbits.utils.notifyApiError(error)
      } finally {
        this.isUploadingTemplate = false
      }
    },

    _getImageDimensions(file) {
      return new Promise((resolve, reject) => {
        const url = URL.createObjectURL(file)
        const img = new Image()
        img.onload = () => {
          resolve({width: img.naturalWidth, height: img.naturalHeight})
          URL.revokeObjectURL(url)
        }
        img.onerror = (err) => {
          URL.revokeObjectURL(url)
          reject(err)
        }
        img.src = url
      })
    },

    async uploadAssetFile(file) {
      const form = new FormData()
      form.append('file', file)
      form.append('public_asset', 'true')
      const {data} = await LNbits.api.request(
        'POST',
        '/api/v1/assets?public_asset=true',
        null,
        form
      )
      return data.id
    },

    // ----- Email delivery dialog -----

    isValidEmail(val) {
      if (!val) return false
      const re = /^[^\s@]+@[^\s@]+\.[^\s@]+$/
      return re.test(val)
    },

    openEmailDialog(card) {
      this.emailDialog.card = card
      this.emailDialog.data = {
        recipient_email: card.recipient_email || '',
        email_mode: 'custom',
        subject: `You have a gift card from ${card.sender_name || 'Anonymous'}`,
        body: '',
        template: 'notification'
      }
      this.emailDialog.show = true
    },

    async sendEmail() {
      if (!this.emailDialog.card) return
      if (!this.isValidEmail(this.emailDialog.data.recipient_email)) {
        LNbits.utils.notify('Enter a valid email address.', 'negative')
        return
      }
      this.emailDialog.loading = true
      try {
        const wallet = this.g.user.wallets.find(w => w.id === this.emailDialog.card.wallet) || this.g.user.wallets[0]
        const url = `/giftcards/api/v1/cards/${this.emailDialog.card.id}/deliver`
        await LNbits.api.request(
          'POST',
          url,
          wallet.adminkey,
          this.emailDialog.data
        )
        this.emailDialog.show = false
        LNbits.utils.notify('Email sent successfully', 'positive')
        this.loadGiftCards()
      } catch (error) {
        LNbits.utils.notifyApiError(error)
      } finally {
        this.emailDialog.loading = false
      }
    }
  }
}