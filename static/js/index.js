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
          expires_at: null,
          designMode: 'none'
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
      bgColor: '#ebedf5',
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
      // Tracks whether templateAssetId points to a freshly-uploaded asset
      // that has NOT yet been saved to a card (staged) vs. one loaded from
      // an existing card design (committed). Staged assets are safe to
      // delete when replaced or when the dialog is cancelled; committed
      // assets are referenced by saved cards and must not be deleted.
      templateAssetStaged: false,
      designLoaded: false,
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
          template: 'notification',
          bg_color: '#1976d2'
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
        card: null,
        cardImageUrl: null
      },
      // Dashboard filters (D-12)
      dashboardFilters: {
        status: null,
        search: '',
        dateFrom: null,
        dateTo: null,
        dateRangeLabel: ''
      },
      dateRange: null,
      // Multi-select (D-14)
      selectedCards: [],
      bulkEmailLoading: false,
      // Bulk email confirmation dialog
      bulkEmailDialog: {
        show: false,
        loading: false,
        scope: 'filtered',
        cards: [],
        selected: [],
        skipped: 0
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
          recipient_email: '',
          designMode: 'none'
        }
      },
      // Delete confirmation dialog
      deleteDialog: {
        show: false,
        loading: false,
        card: null
      },
      // Bulk delete confirmation dialog
      bulkDeleteDialog: {
        show: false,
        loading: false,
        count: 0,
        activeAmount: 0,
        cardIds: []
      }
    }
  },
  computed: {
    giftCardColumns() {
      return [
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
    bgColorEnabled() {
      // Background color only applies to the bundled portrait/landscape
      // templates (custom uploads define their own background image).
      return this.selectedTemplate === 'portrait' || this.selectedTemplate === 'landscape'
    },
    cardPreviewStyle() {
      const style = {width: this.previewWidth + 'px', height: this.previewHeight + 'px'}
      if (this.bgColorEnabled) {
        style.backgroundColor = this.bgColor
      }
      return style
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
    previewTextTransform() {
      // Match the server-side Pillow anchor behavior:
      //   left   → "la" (left-anchored, no shift)
      //   center → "ma" (middle-anchored, shift left by 50%)
      //   right  → "ra" (right-anchored, shift left by 100%)
      // Without this transform, the preview positions the LEFT EDGE of the
      // text at textX, but the server draws the text anchored at the
      // center/right point — causing a positional mismatch.
      if (this.textAlign === 'center') return 'translateX(-50%)'
      if (this.textAlign === 'right') return 'translateX(-100%)'
      return 'none'
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
    },
    statusFilterOptions() {
      // Status dropdown options. 'created' is NOT included — cards are
      // created with status='active' immediately, so no card ever has
      // status='created'. 'cancelled' is deferred to v2 AUDT-02.
      return [
        {label: 'Active', value: 'active'},
        {label: 'Redeemed', value: 'redeemed'},
        {label: 'Expired', value: 'expired'}
      ]
    },
    anyFilterActive() {
      return !!(this.dashboardFilters.status ||
                this.dashboardFilters.search ||
                this.dashboardFilters.dateFrom ||
                this.dashboardFilters.dateTo)
    },
    allSelected() {
      return this.giftCards.length > 0 &&
             this.selectedCards.length === this.giftCards.length
    }
  },
  mounted() {
    this.loadGiftCards()
    this.loadWalletBalance()
  },
  methods: {
    toggleSelectAll(val, rows) {
      if (val) {
        this.selectedCards = [...(rows || this.giftCards)]
      } else {
        this.selectedCards = []
      }
    },
    async loadGiftCards() {
      this.loading = true
      try {
        // Build query string from dashboardFilters (D-12 server-side filtering)
        const params = new URLSearchParams()
        if (this.dashboardFilters.status) {
          params.append('status', this.dashboardFilters.status)
        }
        if (this.dashboardFilters.search) {
          params.append('search', this.dashboardFilters.search)
        }
        if (this.dashboardFilters.dateFrom) {
          params.append('date_from', this.dashboardFilters.dateFrom)
        }
        if (this.dashboardFilters.dateTo) {
          params.append('date_to', this.dashboardFilters.dateTo)
        }
        const queryString = params.toString()
        const url = '/giftcards/api/v1/cards' + (queryString ? '?' + queryString : '')
        // Use the wallet's inkey (invoice key) since GET now accepts invoice key (D-10)
        const wallet = this.g.user.wallets[0]
        const key = wallet.inkey || wallet.adminkey
        const response = await LNbits.api.request('GET', url, key)
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
        expires_at: null,
        designMode: 'none'
      }
      this.createDialog.result = null
      // Reset card designer to defaults
      if (this.templateAssetId && this.templateAssetStaged) {
        this.deleteAssetFile(this.templateAssetId)
      }
      this.templateAssetStaged = false
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
      this.bgColor = '#ebedf5'
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
        const { designMode, ...cardData } = this.createDialog.data
        const payload = {
          ...cardData,
          design: designMode === 'shared' ? this.buildDesignConfig() : null
        }
        const response = await LNbits.api.request(
          'POST',
          '/giftcards/api/v1/cards',
          wallet.adminkey,
          payload
        )
        
        this.createDialog.result = response.data
        await this.loadGiftCards()
        this.loadWalletBalance() // Refresh balance
        // The staged template asset (if any) is now referenced by the saved
        // card → mark it committed so a subsequent reset won't delete it.
        this.templateAssetStaged = false

        Quasar.Notify.create({ message: 'Gift card created successfully!', type: 'positive' })
      } catch (error) {
        LNbits.utils.notifyApiError(error)
      } finally {
        this.createDialog.loading = false
      }
    },

    async copyLink(giftCard) {
      if (giftCard.redemption_url) {
        await this.copyToClipboard(giftCard.redemption_url)
        Quasar.Notify.create({ message: 'Link copied to clipboard', type: 'positive' })
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
        const url = `/giftcards/api/v1/cards/${card.id}/print?t=` + Date.now()
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
        Quasar.Notify.create({ message: 'Gift card image downloaded', type: 'positive' })
      } catch (error) {
        LNbits.utils.notifyApiError(error)
      }
    },

    exportCSV(scope) {
      // scope: 'selected' → export selectedCards, 'filtered' → export
      // current giftCards list, undefined → export all giftCards (legacy)
      let cards
      if (scope === 'selected') {
        cards = this.selectedCards
      } else {
        cards = this.giftCards
      }
      if (cards.length === 0) {
        Quasar.Notify.create({ message: 'No gift cards to export', type: 'warning' })
        return
      }

      const headers = [
        'card_id', 'amount', 'status', 'recipient_name', 'sender_name',
        'message', 'recipient_email', 'email_status', 'redemption_url',
        'created_at', 'expires_at', 'redeemed_at'
      ]
      const rows = cards.map(card => [
        card.id,
        card.amount,
        card.status,
        card.recipient_name || '',
        card.sender_name || '',
        card.message || '',
        card.recipient_email || '',
        card.email_status || '',
        card.redemption_url || '',
        card.created_at || '',
        card.expires_at || '',
        card.redeemed_at || ''
      ])

      let csv = headers.join(',') + '\n'
      rows.forEach(row => {
        csv += row.map(cell => `"${cell}"`).join(',') + '\n'
      })

      const blob = new Blob([csv], {type: 'text/csv'})
      const url = window.URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      const suffix = scope === 'selected' ? 'selected' : (scope === 'filtered' ? 'filtered' : 'all')
      a.download = `giftcards_${suffix}_${new Date().toISOString().split('T')[0]}.csv`
      a.click()
      window.URL.revokeObjectURL(url)

      Quasar.Notify.create({ message: 'CSV exported successfully', type: 'positive' })
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
      if (value === 'portrait' || value === 'landscape') {
        // Switching away from 'custom' abandons the staged upload. Clean it
        // up so it doesn't count against the user's per-user asset cap
        // (only staged assets — committed ones are still referenced by a
        // saved card until the edit is saved).
        if (this.templateAssetId && this.templateAssetStaged) {
          this.deleteAssetFile(this.templateAssetId)
        }
        this.templateAssetStaged = false
        this.templateAssetId = null
        if (value === 'portrait') {
          this.actualTemplateWidth = 425
          this.actualTemplateHeight = 650
          this.previewWidth = 212
          this.previewHeight = 325
          this.templateUrl = '/giftcards/static/image/template_portrait.png'
        } else {
          this.actualTemplateWidth = 1050
          this.actualTemplateHeight = 600
          this.previewWidth = 262
          this.previewHeight = 150
          this.templateUrl = '/giftcards/static/image/template_landscape.png'
        }
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
          Quasar.Notify.create({ message: 'Template image too large. Maximum dimensions are 1500x2000px.', type: 'negative' })
          return
        }
      } catch (err) {
        Quasar.Notify.create({ message: 'Could not read image file.', type: 'negative' })
        return
      }

      this.isUploadingTemplate = true
      try {
        // Replace any previously-staged template asset before uploading the
        // new one. LNbits enforces a per-user asset cap
        // (lnbits_max_assets_per_user, default 1) that only admin users are
        // exempt from. Without this cleanup, non-admin users hit the cap on
        // their first upload and can never change/replace the template image.
        // Only staged (not-yet-saved) assets are deleted here — committed
        // assets (loaded from an existing card) are referenced by saved cards
        // and must not be removed.
        if (this.templateAssetId && this.templateAssetStaged) {
          await this.deleteAssetFile(this.templateAssetId)
        }
        const assetId = await this.uploadAssetFile(file)
        this.templateAssetId = assetId
        this.templateAssetStaged = true
        this.templateUrl = `/giftcards/api/v1/cards/template/${assetId}`
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
        Quasar.Notify.create({ message: 'Custom template uploaded', type: 'positive' })
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
      // Upload to the giftcards extension's own template storage, bypassing
      // the global LNbits asset system (which enforces a per-user cap of
      // lnbits_max_assets_per_user, default 1). Uses the wallet's admin key
      // for authentication, consistent with other giftcards write endpoints.
      const wallet = this.g.user.wallets[0]
      const form = new FormData()
      form.append('file', file)
      const {data} = await LNbits.api.request(
        'POST',
        '/giftcards/api/v1/cards/template',
        wallet.adminkey,
        form
      )
      return data.id
    },

    async deleteAssetFile(assetId) {
      // Delete a template image from the giftcards extension's own storage.
      // Used to clean up orphaned/staged templates when replaced or cancelled.
      // A failure here is non-fatal.
      try {
        const wallet = this.g.user.wallets[0]
        await LNbits.api.request('DELETE', '/giftcards/api/v1/cards/template/' + assetId, wallet.adminkey)
      } catch (error) {
        console.warn('Failed to delete previous template:', error)
      }
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
        template: 'notification',
        bg_color: '#1976d2'
      }
      this.emailDialog.show = true
    },

    async sendEmail() {
      if (!this.emailDialog.card) return
      if (!this.isValidEmail(this.emailDialog.data.recipient_email)) {
        Quasar.Notify.create({ message: 'Enter a valid email address.', type: 'negative' })
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
        Quasar.Notify.create({ message: 'Email sent successfully', type: 'positive' })
        await this.loadGiftCards()
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
      if (this.templateAssetId && this.templateAssetStaged) {
        this.deleteAssetFile(this.templateAssetId)
      }
      this.templateAssetStaged = false
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
      this.bgColor = '#ebedf5'
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
            design = this.buildDesignConfig()
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
          // Staged template asset (if any) is now referenced by the created
          // cards → mark committed so a later reset won't delete it.
          this.templateAssetStaged = false
          Quasar.Notify.create({ message: count + ' gift cards created successfully!', type: 'positive' })
          this.clearFilters()
          this.loadWalletBalance()
        } else {
          // Same-amount mode — existing behavior
          let design = null
          if (this.bulkDialog.sameData.designMode === 'shared') {
            design = this.buildDesignConfig()
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
          this.templateAssetStaged = false
          Quasar.Notify.create({ message: count + ' gift cards created successfully!', type: 'positive' })
          this.clearFilters()
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
        Quasar.Notify.create({ message: 'Please select a CSV file.', type: 'negative' })
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

    async openDetailDialog(card) {
      this.detailDialog.card = card
      this.detailDialog.cardImageUrl = null
      this.detailDialog.show = true
      // Fetch full card details via GET /cards/{id} with admin key (D-13)
      try {
        const wallet = this.g.user.wallets.find(w => w.id === card.wallet) || this.g.user.wallets[0]
        const response = await LNbits.api.request(
          'GET',
          '/giftcards/api/v1/cards/' + card.id + '?include_link=true',
          wallet.adminkey
        )
        this.detailDialog.card = response.data
        // Set card image URL if the card has a token_hash (public image endpoint).
        // Append a cache-busting timestamp so the browser always fetches a
        // fresh image (the design may have been updated since the last view).
        if (response.data.token_hash) {
          this.detailDialog.cardImageUrl = '/giftcards/api/v1/cards/' + response.data.token_hash + '/image?t=' + Date.now()
        }
      } catch (error) {
        // Full detail fetch failed — keep the summary card data already set
        console.error('Failed to load card details:', error)
      }
    },

    async openEditDialog(card) {
      this.editDialog.card = card
      this.editDialog.data = {
        recipient_name: card.recipient_name || '',
        sender_name: card.sender_name || '',
        message: card.message || '',
        recipient_email: card.recipient_email || ''
      }
      // Reset card designer to defaults, then override with the card's
      // existing design config (fetched from the detail endpoint which
      // returns the parsed DesignConfig).
      this.resetCardDesigner()
      this.editDialog.data.designMode = 'none'
      this.designLoaded = false
      this.editDialog.show = true
      try {
        const wallet = this.g.user.wallets.find(w => w.id === card.wallet) || this.g.user.wallets[0]
        const response = await LNbits.api.request(
          'GET',
          '/giftcards/api/v1/cards/' + card.id,
          wallet.adminkey
        )
        const detail = response.data
        if (detail && detail.design) {
          this.applyDesignToDesigner(detail.design)
          this.editDialog.data.designMode = 'shared'
        }
        this.designLoaded = true
      } catch (error) {
        console.error('Failed to load card design for edit:', error)
        Quasar.Notify.create({ message: 'Could not load card design — only metadata will be saved.', type: 'warning' })
      }
    },

    resetCardDesigner() {
      // Clean up a staged (not-yet-saved) template asset so it doesn't
      // count against the user's per-user asset cap (lnbits_max_assets_per_user,
      // default 1). Without this, a non-admin user who uploads a template and
      // then cancels/changes the design would be permanently blocked from
      // uploading another image. Committed assets (saved to a card) are kept.
      if (this.templateAssetId && this.templateAssetStaged) {
        this.deleteAssetFile(this.templateAssetId)
      }
      this.templateAssetStaged = false
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
      this.bgColor = '#ebedf5'
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

    applyDesignToDesigner(design) {
      // Set template + dimensions first so fraction→pixel math is correct.
      if (design.template_name && design.template_name !== 'custom') {
        this.selectedTemplate = design.template_name
        this.onTemplateChange(design.template_name)
      } else if (design.template_name === 'custom') {
        this.selectedTemplate = 'custom'
        // Restore the custom template preview from the asset ID so the
        // preview shows the actual uploaded image and dimensions are
        // available for fraction math (CR-002).
        this.templateAssetId = design.template_asset_id || null
        // Loaded from a saved card → committed, not staged. Must not be
        // deleted on replace/reset (the card still references it).
        this.templateAssetStaged = false
        if (design.template_asset_id) {
          this.templateUrl = '/giftcards/api/v1/cards/template/' + design.template_asset_id
        }
        // Custom template dimensions are not stored in the design config,
        // so we keep the portrait defaults from resetCardDesigner(). The
        // QR/text fractions will be approximate until the user re-uploads
        // or the asset dimensions are fetched. This is acceptable because
        // custom templates are an advanced workflow and the fractions are
        // still relative to the preview area.
      } else {
        this.templateAssetId = design.template_asset_id || null
        this.templateAssetStaged = false
      }
      // QR position (stored as fractions → convert to preview pixels)
      this.qrX = Math.round((design.qr_x_frac || 0.1) * this.previewWidth)
      this.qrY = Math.round((design.qr_y_frac || 0.7) * this.previewHeight)
      this.qrSize = design.qr_size || 150
      // Text position
      this.textX = Math.round((design.text_x_frac || 0.1) * this.previewWidth)
      this.textY = Math.round((design.text_y_frac || 0.1) * this.previewHeight)
      // Text styling
      this.selectedFont = design.font_family || 'DejaVuSans'
      this.fontSize = design.font_size || 24
      this.fontColor = design.font_color || '#000000'
      this.bgColor = design.bg_color || '#ebedf5'
      this.textAlign = design.text_align || 'left'
      this.showAmount = design.show_amount !== false
      this.showRecipient = design.show_recipient !== false
      this.showMessage = design.show_message !== false
    },

    buildDesignConfig() {
      return {
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
        bg_color: this.bgColor,
        text_align: this.textAlign,
        show_amount: this.showAmount,
        show_recipient: this.showRecipient,
        show_message: this.showMessage
      }
    },

    async saveCardEdit() {
      if (!this.editDialog.card) return
      this.editDialog.loading = true
      try {
        const wallet = this.g.user.wallets.find(w => w.id === this.editDialog.card.wallet) || this.g.user.wallets[0]
        const url = '/giftcards/api/v1/cards/' + this.editDialog.card.id
        const { designMode, ...editData } = this.editDialog.data
        const payload = { ...editData }
        // Only send design if it was successfully loaded from the server.
        // If the fetch failed, sending default design values would silently
        // overwrite the card's actual design (CR-001).
        if (this.designLoaded) {
          if (designMode === 'shared') {
            payload.design = this.buildDesignConfig()
          } else {
            payload.clear_design = true
          }
        }
        await LNbits.api.request(
          'PUT',
          url,
          wallet.adminkey,
          payload
        )
        this.editDialog.show = false
        // A newly-uploaded template asset (if any) is now referenced by the
        // updated card → mark it committed so resetCardDesigner won't delete it.
        this.templateAssetStaged = false
        Quasar.Notify.create({ message: 'Card updated successfully', type: 'positive' })
        await this.loadGiftCards()
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
        Quasar.Notify.create({ message: 'Card deleted and ' + reclaimed + ' sats reclaimed', type: 'positive' })
        await this.loadGiftCards()
        this.loadWalletBalance()
      } catch (error) {
        LNbits.utils.notifyApiError(error)
      } finally {
        this.deleteDialog.loading = false
      }
    },

    openBulkDeleteDialog() {
      if (!this.bulkDeleteDialog || this.selectedCards.length === 0) return
      const activeCards = this.selectedCards.filter(c => c.status === 'active')
      this.bulkDeleteDialog.count = this.selectedCards.length
      this.bulkDeleteDialog.activeAmount = activeCards.reduce((sum, c) => sum + (c.amount || 0), 0)
      this.bulkDeleteDialog.cardIds = this.selectedCards.map(c => c.id)
      this.bulkDeleteDialog.show = true
    },

    async confirmBulkDelete() {
      if (!this.bulkDeleteDialog || this.bulkDeleteDialog.cardIds.length === 0) return
      this.bulkDeleteDialog.loading = true
      try {
        const wallet = this.g.user.wallets[0]
        const response = await LNbits.api.request(
          'DELETE',
          '/giftcards/api/v1/cards/bulk',
          wallet.adminkey,
          { card_ids: this.bulkDeleteDialog.cardIds }
        )
        this.bulkDeleteDialog.show = false
        const deleted = response.data.deleted || 0
        const reclaimed = response.data.reclaimed_sats || 0
        let msg = deleted + ' card' + (deleted === 1 ? '' : 's') + ' deleted'
        if (reclaimed > 0) {
          msg += ' and ' + reclaimed + ' sats reclaimed'
        }
        Quasar.Notify.create({ message: msg, type: 'positive' })
        this.selectedCards = []
        await this.loadGiftCards()
        this.loadWalletBalance()
      } catch (error) {
        LNbits.utils.notifyApiError(error)
      } finally {
        this.bulkDeleteDialog.loading = false
      }
    },

    // ----- Dashboard filters (D-12) -----

    applyFilters() {
      this.selectedCards = []
      this.loadGiftCards()
    },

    clearFilters() {
      this.dashboardFilters = {
        status: null,
        search: '',
        dateFrom: null,
        dateTo: null,
        dateRangeLabel: ''
      }
      this.dateRange = null
      this.selectedCards = []
      this.loadGiftCards()
    },

    applyDateRange() {
      // q-date range mode returns {from, to} or null
      const from = this.dateRange?.from || null
      const to = this.dateRange?.to || null
      this.dashboardFilters.dateFrom = from
      this.dashboardFilters.dateTo = to
      if (from && to) {
        this.dashboardFilters.dateRangeLabel = from + ' — ' + to
      } else if (from) {
        this.dashboardFilters.dateRangeLabel = 'From ' + from
      } else if (to) {
        this.dashboardFilters.dateRangeLabel = 'Until ' + to
      } else {
        this.dashboardFilters.dateRangeLabel = ''
      }
      this.applyFilters()
    },

    clearDateRange() {
      this.dateRange = null
      this.dashboardFilters.dateFrom = null
      this.dashboardFilters.dateTo = null
      this.dashboardFilters.dateRangeLabel = ''
      this.applyFilters()
    },

    // ----- Bulk email sending (D-04, D-14) -----

    sendBulkEmails(scope) {
      // scope: 'selected' → use selectedCards, 'filtered' → use giftCards
      let targetCards
      if (scope === 'selected') {
        targetCards = this.selectedCards
      } else {
        targetCards = this.giftCards
      }
      const emailable = targetCards.filter(c => c.recipient_email)
      const skipped = targetCards.length - emailable.length
      this.bulkEmailDialog.scope = scope
      this.bulkEmailDialog.cards = emailable
      this.bulkEmailDialog.selected = [...emailable]
      this.bulkEmailDialog.skipped = skipped
      this.bulkEmailDialog.show = true
    },

    async confirmBulkEmails() {
      this.bulkEmailDialog.loading = true
      this.bulkEmailLoading = true
      let sent = 0
      let failed = 0
      try {
        for (const card of this.bulkEmailDialog.selected) {
          try {
            const wallet = this.g.user.wallets.find(w => w.id === card.wallet) || this.g.user.wallets[0]
            const url = '/giftcards/api/v1/cards/' + card.id + '/deliver'
            await LNbits.api.request('POST', url, wallet.adminkey, {
              recipient_email: card.recipient_email,
              email_mode: 'custom',
              subject: 'You have a gift card from ' + (card.sender_name || 'Anonymous'),
              body: ''
            })
            sent++
          } catch (err) {
            failed++
          }
        }
        const skipped = this.bulkEmailDialog.skipped
        const msg = sent + ' emails sent, ' + skipped + ' skipped (no email address)'
        if (failed > 0) {
          Quasar.Notify.create({ message: msg + ', ' + failed + ' failed', type: 'warning' })
        } else {
          Quasar.Notify.create({ message: msg, type: 'positive' })
        }
        this.bulkEmailDialog.show = false
        await this.loadGiftCards()
      } catch (error) {
        LNbits.utils.notifyApiError(error)
      } finally {
        this.bulkEmailDialog.loading = false
        this.bulkEmailLoading = false
      }
    }
  }
}