<template id="page-giftcards-claim">
  <div class="row justify-center">
    <div class="col-12 col-md-7 col-lg-6 q-gutter-y-md">
      <!-- State A: Email entry (initial) -->
      <q-card v-if="claimState === 'entry'" class="q-pa-lg">
        <q-card-section class="q-pa-none">
          <div class="text-center">
            <q-icon name="card_giftcard" color="primary" size="48px"></q-icon>
            <h5 class="text-h6 q-mt-md">Claim Your Gift Card</h5>
            <p class="text-body2 text-grey">Enter your email to receive a verification link for any pending gift cards.</p>
            <q-form @submit="submitClaim">
              <q-input
                filled
                dense
                v-model.trim="email"
                type="email"
                label="Your Email"
                :rules="[val => !!val && isValidEmail(val) || 'Enter a valid email address']"
              ></q-input>
              <q-btn
                unelevated
                color="primary"
                size="lg"
                type="submit"
                label="Send Verification Link"
                :loading="submitting"
                class="q-mt-md"
              ></q-btn>
            </q-form>
          </div>
        </q-card-section>
      </q-card>

      <!-- State B: Check your email (confirmation — D-14) -->
      <q-card v-else-if="claimState === 'confirm'" class="q-pa-lg">
        <q-card-section class="q-pa-none">
          <div class="text-center">
            <q-icon name="mark_email_read" color="positive" size="64px"></q-icon>
            <h5 class="text-h6 q-mt-md">Check Your Email</h5>
            <p class="text-body2 text-grey">If you have pending gift cards, a verification link has been sent to {{ email }}. The link expires in 30 minutes.</p>
            <q-btn flat color="grey" label="Use a different email" @click="resetClaim"></q-btn>
          </div>
        </q-card-section>
      </q-card>

      <!-- State C: Rate limit exceeded (429) -->
      <q-card v-else-if="claimState === 'rate_limited'" class="q-pa-lg">
        <q-card-section class="q-pa-none">
          <div class="text-center">
            <q-icon name="hourglass_empty" color="warning" size="64px"></q-icon>
            <h5 class="text-h6 q-mt-md">Too Many Requests</h5>
            <p class="text-body2 text-grey">You've requested too many verification links. Please wait an hour and try again.</p>
            <q-btn flat color="grey" label="Back" @click="resetClaim"></q-btn>
          </div>
        </q-card-section>
      </q-card>

      <!-- State D: Loading -->
      <q-card v-else-if="claimState === 'loading'" class="q-pa-lg">
        <q-card-section class="q-pa-none">
          <div class="text-center">
            <q-spinner color="primary" size="48px"></q-spinner>
          </div>
        </q-card-section>
      </q-card>

      <!-- State E: Pending cards list (D-15) -->
      <q-card v-else-if="claimState === 'cards'" class="q-pa-lg">
        <q-card-section class="q-pa-none">
          <div class="text-center q-mb-md">
            <q-icon name="card_giftcard" color="primary" size="48px"></q-icon>
            <h5 class="text-h6 q-mt-md">You Have {{ pendingCards.length }} Gift Card(s) Waiting</h5>
            <p class="text-body2 text-grey">Click Redeem to claim your gift card.</p>
          </div>
          <q-card v-for="card in pendingCards" :key="card.id" class="q-mb-md">
            <q-card-section>
              <div class="row items-center no-wrap">
                <div class="col">
                  <div class="text-h6">{{ card.amount }} sats</div>
                  <div class="text-body2">From: {{ card.sender_name || 'Anonymous' }}</div>
                  <div class="text-body2" v-if="card.message">{{ card.message }}</div>
                  <div class="text-caption q-mt-sm">Received: {{ formatDate(card.created_at) }}</div>
                </div>
                <div class="col-auto">
                  <q-btn
                    unelevated
                    color="primary"
                    label="Redeem Gift Card"
                    :href="'/giftcards/redeem/' + card.raw_token"
                  ></q-btn>
                </div>
              </div>
            </q-card-section>
          </q-card>
          <div v-if="pendingCards.length === 0" class="text-center">
            <q-icon name="inbox" color="grey-6" size="64px"></q-icon>
            <h5 class="text-h6 q-mt-md">No Pending Gift Cards</h5>
            <p class="text-body2 text-grey">There are no gift cards waiting for you at this time.</p>
          </div>
        </q-card-section>
      </q-card>

      <!-- State F: Invalid or expired magic link -->
      <q-card v-else-if="claimState === 'invalid'" class="q-pa-lg">
        <q-card-section class="q-pa-none">
          <div class="text-center">
            <q-icon name="link_off" color="negative" size="64px"></q-icon>
            <h5 class="text-h6 q-mt-md">Link Invalid or Expired</h5>
            <p class="text-body2 text-grey">This verification link is invalid or has expired. Request a new link below.</p>
            <q-btn unelevated color="primary" label="Request New Link" @click="$router.push('/giftcards/claim')"></q-btn>
          </div>
        </q-card-section>
      </q-card>
    </div>
  </div>
</template>
