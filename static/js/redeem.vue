<template id="page-giftcards-redeem">
  <div class="row justify-center">
    <div class="col-12 col-md-7 col-lg-6 q-gutter-y-md">
      <!-- Loading State -->
      <q-card class="q-pa-lg" v-if="loading">
        <q-card-section class="q-pa-none">
          <div class="text-center">
            <q-spinner color="primary" size="48px"></q-spinner>
          </div>
        </q-card-section>
      </q-card>

      <!-- Callback Error State -->
      <q-card class="q-pa-lg" v-else-if="giftCard && giftCard.status === 'active' && error">
        <q-card-section class="q-pa-none">
          <div class="text-center">
            <q-icon name="error_outline" color="negative" size="64px"></q-icon>
            <h5 class="text-h6 q-mt-md">Redemption failed</h5>
            <p class="text-body2 text-grey">
              Redemption failed. Please scan the QR code again or try a different wallet.
            </p>
            <q-btn
              unelevated
              color="primary"
              size="lg"
              @click="clearError"
            >
              Try Again
            </q-btn>
          </div>
        </q-card-section>
      </q-card>

      <!-- Active State -->
      <q-card class="q-pa-lg" v-else-if="giftCard && giftCard.status === 'active'">
        <q-card-section class="q-pa-none">
          <div class="text-center">
            <h5 class="text-h5 q-my-none">{{ giftCard.amount }} sats</h5>
            
            <p class="text-body2 q-mt-md" v-if="giftCard.sender_name">
              From {{ giftCard.sender_name }}
            </p>
            
            <p class="text-body2 q-mt-md" v-if="giftCard.message">
              {{ giftCard.message }}
            </p>
            
            <p class="text-caption q-mt-sm" v-if="giftCard.recipient_name">
              For {{ giftCard.recipient_name }}
            </p>
            
            <q-separator class="q-my-md"></q-separator>
            
            <img
              v-if="giftCard && giftCard.has_design"
              :src="cardImageUrl"
              alt="Branded gift card with QR code"
              class="branded-card-img"
            />

            <p class="text-body2 q-mt-md" v-if="!giftCard || !giftCard.has_design">
              Scan with your Lightning wallet to redeem:
            </p>
            
            <div class="row justify-center q-mb-md" v-if="!giftCard || !giftCard.has_design">
              <img
                :src="qrCodeUrl"
                alt="LNURL QR code for gift card redemption"
                class="qrcode-img"
                :style="{ width: qrSize + 'px', height: qrSize + 'px' }"
              />
            </div>
            
            <q-btn
              unelevated
              color="primary"
              size="lg"
              class="q-mb-md"
              :href="lightningUri"
              v-if="lightningUri"
            >
              Redeem via Lightning Wallet
            </q-btn>
            
            <q-separator class="q-my-md"></q-separator>
            
            <p class="text-caption">
              Expires: {{ giftCard.expires_at ? formatDate(giftCard.expires_at) : 'No expiration' }}
            </p>
          </div>
        </q-card-section>
      </q-card>

      <!-- Redeemed State -->
      <q-card class="q-pa-lg" v-else-if="giftCard && giftCard.status === 'redeemed'">
        <q-card-section class="q-pa-none">
          <div class="text-center">
            <q-icon name="check_circle" color="positive" size="64px"></q-icon>
            <h5 class="text-h6 q-mt-md">This gift card has been redeemed</h5>
            <p class="text-body2 text-grey">
              This card was already redeemed. If you believe this is an error, contact the sender.
            </p>
          </div>
        </q-card-section>
      </q-card>

      <!-- Expired State -->
      <q-card class="q-pa-lg" v-else-if="giftCard && giftCard.status === 'expired'">
        <q-card-section class="q-pa-none">
          <div class="text-center">
            <q-icon name="schedule" color="warning" size="64px"></q-icon>
            <h5 class="text-h6 q-mt-md">This gift card has expired</h5>
            <p class="text-body2 text-grey">
              The card expired on {{ formatDate(giftCard.expired_at) }}. The sats have been returned to the issuer.
            </p>
          </div>
        </q-card-section>
      </q-card>

      <!-- Not Found State -->
      <q-card class="q-pa-lg" v-else>
        <q-card-section class="q-pa-none">
          <div class="text-center">
            <q-icon name="error_outline" color="negative" size="64px"></q-icon>
            <h5 class="text-h6 q-mt-md">Gift card not found</h5>
            <p class="text-body2 text-grey">
              This link may be invalid or the card may have been removed. Check the link and try again.
            </p>
          </div>
        </q-card-section>
      </q-card>
    </div>
  </div>
</template>

<style>
.qrcode-img {
  max-width: 300px;
  max-height: 300px;
}

.branded-card-img {
  max-width: 400px;
  width: 100%;
  height: auto;
}

@media (max-width: 768px) {
  .qrcode-img {
    max-width: 240px;
    max-height: 240px;
  }
  .branded-card-img {
    max-width: 320px;
  }
}
</style>