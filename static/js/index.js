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
      actualTemplateWidth: 425,
      actualTemplateHeight: 650,
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
      },
      // Bulk create dialog
      bulkDialog: {
        show: false,
        loading: false,
        activeTab: 'same',
        sameData: {
          wallet: null,
          count: null,
          amount: null,
          recipient_name: '',
          sender_name: '',
          message: '',
          expires_at: null,
          designMode: 'none'
        },
        csvData: {
          designMode: 'none'
        },
        csvFile: null,
        csvRows: [],
        csvErrors: 0,
        csvParsing: false,
        csvErrorRows: []
      },
      // Card detail dialog
      detailDialog: {
        show: false,
        card: null
      },
      // Card edit dialog
      editDialog: {
        show: false,
        loading: false,
        card: null,
        data: {
          recipient_name: '',
          sender_name: '',
          message: '',
          recipient_email: ''
        }
      },
      // Delete confirmation dialog
      deleteDialog: {
        show: false,
        loading: false,
        card: null
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
    previewScale() {
      if (!this.actualTemplateWidth) return 1
      return this.previewWidth / this.actualTemplateWidth
    },
    previewQrSize() {
      // qrSize is tracked in ACTUAL card pixels; the preview renders it
      // scaled down by previewScale so the on-screen QR matches what the
      // server will actually render on the real card.
      return Math.round(this.qrSize * this.previewScale)
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
        fontSize: Math.round(this.fontSize * this.previewScale) + 'px',
        color: this.fontColor,
        textAlign: alignMap[this.textAlign] || 'left',
        lineHeight: '1.3'
      }
    },
    bulkSubmitLabel() {
      if (this.bulkDialog.activeTab === 'csv') {
        const validCount = this.bulkDialog.csvRows.length
        return 'Create ' + validCount + ' Cards'
      }
      return 'Create ' + (this.bulkDialog.sameData.count || 0) + ' Cards'
    },
    bulkSubmitDisabled() {
      if (this.bulkDialog.activeTab === 'csv') {
        return this.bulkDialog.csvErrors > 0 ||
               this.bulkDialog.csvRows.length === 0 ||
               this.bulkDialog.csvRows.length > 500
      }
      const count = this.bulkDialog.sameData.count
      const amount = this.bulkDialog.sameData.amount
      return count <= 0 || amount <= 0 || (count * amount > this.walletBalance)
    },
    bulkTotalExceedsBalance() {
      const count = this.bulkDialog.sameData.count || 0
      const amount = this.bulkDialog.sameData.amount || 0
      return count * amount > this.walletBalance
    },
    csvValidationColumns() {
      return [
        {name: 'rowIndex', align: 'left', label: '#', field: 'rowIndex', sortable: false},
        {name: 'status', align: 'left', label: 'Status', field: 'valid', sortable: false},
        {name: 'recipient_name', align: 'left', label: 'Recipient', field: 'recipient_name', sortable: false},
        {name: 'amount_sats', align: 'right', label: 'Amount', field: 'amount_sats', sortable: false},
        {name: 'recipient_email', align: 'left', label: 'Email', field: 'recipient_email', sortable: false},
        {name: 'nostr_npub', align: 'left', label: 'Npub', field: 'nostr_npub', sortable: false},
        {name: 'errors', align: 'left', label: 'Errors', field: 'errors', sortable: false}
      ]
    },
    csvValidationTableRows() {
      // Combine valid rows and error rows into a single table data source
      const validRows = this.bulkDialog.csvRows.map(r => ({
        rowIndex: r.row_num,
        valid: true,
        recipient_name: r.recipient_name,
        amount_sats: r.amount_sats,
        recipient_email: r.recipient_email,
        nostr_npub: r.nostr_npub,
        errors: []
      }))
      const errorRows = this.bulkDialog.csvErrorRows.map(e => ({
        rowIndex: e.row_num,
        valid: false,
        recipient_name: '',
        amount_sats: '',
        recipient_email: '',
        nostr_npub: '',
        errors: [e.field + ': ' + e.message]
      }))
      // Merge and sort by row index
      return [...validRows, ...errorRows].sort((a, b) => a.rowIndex - b.rowIndex)
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
      this.actualTemplateWidth = 425
      this.actualTemplateHeight = 650
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
        case 'created': return 'grey-6'
        case 'redeemed': return 'grey-6'
        case 'expired': return 'warning'
        default: return 'grey'
      }
    },

    getStatusText(status) {
      switch (status) {
        case 'active': return 'Active'
        case 'created': return 'Created'
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
        const pqrs = this.previewQrSize
        this.qrX = Math.max(0, Math.min(newX, this.previewWidth - pqrs))
        this.qrY = Math.max(0, Math.min(newY, this.previewHeight - pqrs))
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
      // dx is in preview pixels; convert to actual card pixels so qrSize
      // stays in the same units the server renderer uses.
      const scale = this.previewScale || 1
      const deltaActual = dx / scale
      const newSize = Math.max(this.minQrSize, this.resizeState.origSize + deltaActual)
      // Clamp so the QR doesn't overflow the preview's right edge.
      const maxPreviewSize = this.previewWidth - this.qrX
      const maxActualSize = maxPreviewSize / scale
      this.qrSize = Math.min(newSize, maxActualSize)
    },

    endResize() {
      this.resizeState = null
    },

    // ----- Card Designer: template selection & upload -----

    onTemplateChange(value) {
      if (value === 'portrait') {
        this.actualTemplateWidth = 425
        this.actualTemplateHeight = 650
        this.previewWidth = 212
        this.previewHeight = 325
        this.templateUrl = '/giftcards/static/image/template_portrait.png'
        this.templateAssetId = null
      } else if (value === 'landscape') {
        this.actualTemplateWidth = 1050
        this.actualTemplateHeight = 600
        this.previewWidth = 262
        this.previewHeight = 150
        this.templateUrl = '/giftcards/static/image/template_landscape.png'
        this.templateAssetId = null
      }
      // Reset QR/text positions to default fractions so they're on-card
      // after a dimension change (old pixel positions may be off-screen).
      this.qrX = Math.round(0.1 * this.previewWidth)
      this.qrY = Math.round(0.7 * this.previewHeight)
      this.textX = Math.round(0.1 * this.previewWidth)
      this.textY = Math.round(0.1 * this.previewHeight)
      // 'custom' — actual + preview dimensions set in handleTemplateSelected
    },

    triggerTemplateUpload() {
      this.$refs.templateUpload.value = null
      this.$refs.templateUpload.click()
    },

    async handleTemplateSelected(event) {
      const file = event.target.files && event.target.files[0]
      if (!file) return

      // D-03: validate image dimensions (max 1500x2000px) client-side
      let dims
      try {
        dims = await this._getImageDimensions(file)
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
        // Track actual dimensions and fit a preview that preserves aspect ratio
        // within a ~325px max dimension so the QR scale stays accurate.
        this.actualTemplateWidth = dims.width
        this.actualTemplateHeight = dims.height
        const maxPreview = 325
        if (dims.width >= dims.height) {
          this.previewWidth = maxPreview
          this.previewHeight = Math.round(maxPreview * dims.height / dims.width)
        } else {
          this.previewHeight = maxPreview
          this.previewWidth = Math.round(maxPreview * dims.width / dims.height)
        }
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
    },

    // ----- Bulk create dialog -----

    openBulkDialog() {
      this.bulkDialog.show = true
      this.bulkDialog.activeTab = 'same'
      this.bulkDialog.sameData = {
        wallet: this.g.user.wallets.length > 0 ? this.g.user.wallets[0].id : null,
        count: null,
        amount: null,
        recipient_name: '',
        sender_name: '',
        message: '',
        expires_at: null,
        designMode: 'none'
      }
      this.bulkDialog.csvFile = null
      this.bulkDialog.csvRows = []
      this.bulkDialog.csvErrors = 0
      this.bulkDialog.csvErrorRows = []
      this.bulkDialog.csvData = {designMode: 'none'}
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
      this.actualTemplateWidth = 425
      this.actualTemplateHeight = 650
    },

    async submitBulkCreate() {
      this.bulkDialog.loading = true
      try {
        const wallet = this.g.user.wallets.find(w => w.id === this.bulkDialog.sameData.wallet)

        if (this.bulkDialog.activeTab === 'csv') {
          // CSV mode — post validated rows to /cards/bulk
          let design = null
          if (this.bulkDialog.csvData.designMode === 'shared') {
            design = {
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
          }
          const payload = {
            rows: this.bulkDialog.csvRows,
            design_mode: this.bulkDialog.csvData.designMode,
            design: design
          }
          await LNbits.api.request(
            'POST',
            '/giftcards/api/v1/cards/bulk',
            wallet.adminkey,
            payload
          )
          this.bulkDialog.show = false
          const count = this.bulkDialog.csvRows.length
          LNbits.utils.notify(count + ' gift cards created successfully!', 'positive')
          this.loadGiftCards()
          this.loadWalletBalance()
        } else {
          // Same-amount mode — existing behavior
          let design = null
          if (this.bulkDialog.sameData.designMode === 'shared') {
            design = {
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
          }
          const payload = {
            count: this.bulkDialog.sameData.count,
            amount: this.bulkDialog.sameData.amount,
            recipient_name: this.bulkDialog.sameData.recipient_name || null,
            sender_name: this.bulkDialog.sameData.sender_name || null,
            message: this.bulkDialog.sameData.message || null,
            expires_at: this.bulkDialog.sameData.expires_at || null,
            design: design
          }
          await LNbits.api.request(
            'POST',
            '/giftcards/api/v1/cards/bulk',
            wallet.adminkey,
            payload
          )

          this.bulkDialog.show = false
          const count = this.bulkDialog.sameData.count
          LNbits.utils.notify(count + ' gift cards created successfully!', 'positive')
          this.loadGiftCards()
          this.loadWalletBalance()
        }
      } catch (error) {
        LNbits.utils.notifyApiError(error)
      } finally {
        this.bulkDialog.loading = false
      }
    },

    // ----- CSV upload -----

    async onCsvFileSelected(file) {
      if (!file) return
      const filename = file.name || ''
      if (!filename.toLowerCase().endsWith('.csv')) {
        LNbits.utils.notify('Please select a CSV file.', 'negative')
        return
      }
      this.bulkDialog.csvParsing = true
      try {
        const wallet = this.g.user.wallets.find(w => w.id === this.bulkDialog.sameData.wallet) || this.g.user.wallets[0]
        const formData = new FormData()
        formData.append('file', file)
        const response = await LNbits.api.request(
          'POST',
          '/giftcards/api/v1/cards/validate-csv',
          wallet.adminkey,
          formData
        )
        this.bulkDialog.csvRows = response.data.valid_rows || []
        this.bulkDialog.csvErrorRows = response.data.errors || []
        this.bulkDialog.csvErrors = response.data.error_count || 0
      } catch (error) {
        LNbits.utils.notifyApiError(error)
        this.bulkDialog.csvRows = []
        this.bulkDialog.csvErrorRows = []
        this.bulkDialog.csvErrors = 0
      } finally {
        this.bulkDialog.csvParsing = false
      }
    },

    downloadCsvTemplate() {
      const headers = 'recipient_name,amount_sats,recipient_email,nostr_npub,sender_name,message'
      const exampleRow = 'Alice,1000,alice@example.com,,Bob,Happy birthday!'
      const csv = headers + '\n' + exampleRow + '\n'
      const blob = new Blob([csv], {type: 'text/csv'})
      const url = window.URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = 'giftcards_bulk_template.csv'
      a.click()
      window.URL.revokeObjectURL(url)
    },

    // ----- Card detail / edit / delete dialogs -----

    openDetailDialog(card) {
      this.detailDialog.card = card
      this.detailDialog.show = true
    },

    openEditDialog(card) {
      this.editDialog.card = card
      this.editDialog.data = {
        recipient_name: card.recipient_name || '',
        sender_name: card.sender_name || '',
        message: card.message || '',
        recipient_email: card.recipient_email || ''
      }
      this.editDialog.show = true
    },

    async saveCardEdit() {
      if (!this.editDialog.card) return
      this.editDialog.loading = true
      try {
        const wallet = this.g.user.wallets.find(w => w.id === this.editDialog.card.wallet) || this.g.user.wallets[0]
        const url = '/giftcards/api/v1/cards/' + this.editDialog.card.id
        await LNbits.api.request(
          'PUT',
          url,
          wallet.adminkey,
          this.editDialog.data
        )
        this.editDialog.show = false
        LNbits.utils.notify('Card updated successfully', 'positive')
        this.loadGiftCards()
      } catch (error) {
        LNbits.utils.notifyApiError(error)
      } finally {
        this.editDialog.loading = false
      }
    },

    openDeleteDialog(card) {
      this.deleteDialog.card = card
      this.deleteDialog.show = true
    },

    async confirmDelete() {
      if (!this.deleteDialog.card) return
      this.deleteDialog.loading = true
      try {
        const wallet = this.g.user.wallets.find(w => w.id === this.deleteDialog.card.wallet) || this.g.user.wallets[0]
        const url = '/giftcards/api/v1/cards/' + this.deleteDialog.card.id
        const response = await LNbits.api.request(
          'DELETE',
          url,
          wallet.adminkey
        )
        this.deleteDialog.show = false
        const reclaimed = response.data.reclaimed_sats || 0
        LNbits.utils.notify('Card deleted and ' + reclaimed + ' sats reclaimed', 'positive')
        this.loadGiftCards()
        this.loadWalletBalance()
      } catch (error) {
        LNbits.utils.notifyApiError(error)
      } finally {
        this.deleteDialog.loading = false
      }
    }
  }
}