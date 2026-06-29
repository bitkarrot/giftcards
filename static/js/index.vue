<template id="page-giftcards">
  <div class="row q-col-gutter-md">
    <div class="col-12 col-md-8 col-lg-7 q-gutter-y-md">
      <q-card>
        <q-card-section>
          <q-btn
            unelevated
            color="primary"
            label="Create Gift Card"
            @click="openCreateDialog"
          ></q-btn>
        </q-card-section>
      </q-card>

      <q-card>
        <q-card-section>
          <div class="row items-center no-wrap q-mb-md">
            <div class="col">
              <h5 class="text-subtitle1 q-my-none">Gift Cards</h5>
            </div>
            <div class="col-auto">
              <q-btn
                flat
                color="grey"
                @click="exportCSV"
                label="Export CSV"
              ></q-btn>
            </div>
          </div>
          <q-table
            dense
            flat
            :rows="giftCards"
            row-key="id"
            :columns="giftCardColumns"
            v-model:pagination="tablePagination"
            :loading="loading"
          >
            <template v-slot:header="props">
              <q-tr :props="props">
                <q-th auto-width></q-th>
                <q-th v-for="col in props.cols" :key="col.name" :props="props">
                  <span v-text="col.label"></span>
                </q-th>
                <q-th auto-width></q-th>
              </q-tr>
            </template>
            <template v-slot:body="props">
              <q-tr :props="props">
                <q-td auto-width>
                  <q-btn
                    size="sm"
                    color="accent"
                    round
                    dense
                    @click="props.expand = !props.expand"
                    :icon="props.expand ? 'expand_less' : 'expand_more'"
                  />
                </q-td>
                <q-td v-for="col in props.cols" :key="col.name" :props="props">
                  <span v-if="col.name === 'amount'">{{ col.value }} sats</span>
                  <span v-else-if="col.name === 'status'">
                    <q-badge
                      :color="getStatusColor(col.value)"
                      :label="getStatusText(col.value)"
                    />
                  </span>
                  <span v-else-if="col.name === 'expires_at'">
                    {{ col.value || 'Never' }}
                  </span>
                  <span v-else v-text="col.value"></span>
                </q-td>
                <q-td auto-width>
                  <q-btn
                    unelevated
                    dense
                    size="xs"
                    icon="link"
                    :color="$q.dark.isActive ? 'grey-7' : 'grey-5'"
                    @click="copyLink(props.row)"
                    aria-label="Copy redemption link"
                  >
                    <q-tooltip>Copy redemption link</q-tooltip>
                  </q-btn>
                </q-td>
              </q-tr>
              <q-tr v-show="props.expand" :props="props">
                <q-td colspan="100%">
                  <div class="q-pa-md">
                    <div class="row q-col-gutter-md">
                      <div class="col-12 col-md-6">
                        <div class="text-caption">From:</div>
                        <div>{{ props.row.sender_name || 'Anonymous' }}</div>
                      </div>
                      <div class="col-12 col-md-6">
                        <div class="text-caption">Message:</div>
                        <div>{{ props.row.message || 'No message' }}</div>
                      </div>
                      <div class="col-12">
                        <div class="text-caption">Created:</div>
                        <div>{{ formatDate(props.row.created_at) }}</div>
                      </div>
                      <div class="col-12" v-if="props.row.redemption_url">
                        <div class="text-caption">Redemption Link:</div>
                        <q-input
                          readonly
                          dense
                          :value="props.row.redemption_url"
                          outlined
                        >
                          <template v-slot:append>
                            <q-btn
                              flat
                              dense
                              icon="content_copy"
                              @click="copyToClipboard(props.row.redemption_url)"
                              aria-label="Copy link to clipboard"
                            />
                          </template>
                        </q-input>
                      </div>
                    </div>
                  </div>
                </q-td>
              </q-tr>
            </template>
          </q-table>
        </q-card-section>
      </q-card>
    </div>
    
    <div class="col-12 col-md-4 col-lg-5 q-gutter-y-md">
      <q-card>
        <q-card-section>
          <h6 class="text-subtitle1 ellipsis q-my-none">
            Gift Cards Extension
          </h6>
        </q-card-section>
        <q-card-section class="q-pa-none">
          <q-separator></q-separator>
          <q-list>
            <q-expansion-item
              group="extras"
              icon="info"
              label="About Gift Cards"
              :content-inset-level="0.5"
            >
              <q-card>
                <q-card-section>
                  <h5 class="text-subtitle1 q-my-none">How Gift Cards Work</h5>
                  <p>
                    Create sats-denominated gift cards with unique secure redemption links.
                    The recipient can redeem the sats via Lightning without needing an account.
                  </p>
                  <p>
                    <small>
                      Created for LNBits by the giftcards extension team
                    </small>
                  </p>
                </q-card-section>
              </q-card>
            </q-expansion-item>
          </q-list>
        </q-card-section>
      </q-card>
    </div>

    <!-- Create Gift Card Dialog -->
    <q-dialog v-model="createDialog.show" position="top">
      <q-card class="q-pa-lg q-pt-xl lnbits__dialog-card">
        <q-form @submit="createGiftCard" class="q-gutter-md">
          <div v-if="!createDialog.result">
            <div class="row">
              <div class="col">
                <q-select
                  filled
                  dense
                  emit-value
                  v-model="createDialog.data.wallet"
                  :options="g.user.walletOptions"
                  label="Wallet"
                />
              </div>
            </div>

            <q-input
              filled
              dense
              v-model.number="createDialog.data.amount"
              type="number"
              label="Amount (sats)"
              hint="Sats will be locked from your wallet at creation."
              :rules="[
                val => val > 0 || 'Amount must be greater than 0',
                val => val <= walletBalance || 'Amount exceeds your wallet balance'
              ]"
            />

            <q-input
              filled
              dense
              v-model.trim="createDialog.data.recipient_name"
              type="text"
              label="Recipient Name"
              hint="Optional — shown on the redemption page."
            />

            <q-input
              filled
              dense
              v-model.trim="createDialog.data.sender_name"
              type="text"
              label="Your Name"
              hint="Optional — shown as sender on the redemption page."
            />

            <q-input
              filled
              dense
              v-model.trim="createDialog.data.message"
              type="textarea"
              label="Personal Message"
              hint="Optional — shown to recipient."
            />

            <q-input
              filled
              dense
              v-model="createDialog.data.expires_at"
              type="date"
              label="Expires On"
              hint="No date = card never expires."
              :rules="[
                val => !val || new Date(val) > new Date() || 'Expiration date must be in the future'
              ]"
            />

            <div class="row q-mt-lg">
              <q-btn
                unelevated
                color="primary"
                type="submit"
                label="Create Gift Card"
                :loading="createDialog.loading"
              />
              <q-btn
                v-close-popup
                flat
                color="grey"
                class="q-ml-auto"
                label="Discard Gift Card"
              />
            </div>
          </div>

          <!-- Success Result -->
          <div v-else>
            <div class="text-center q-mb-lg">
              <h5 class="text-h6 q-my-none text-positive">Gift Card Created</h5>
            </div>

            <q-banner class="q-mb-md bg-warning text-white">
              <template v-slot:avatar>
                <q-icon name="warning" />
              </template>
              Save this link — it cannot be recovered.
            </q-banner>

            <q-input
              readonly
              dense
              :value="createDialog.result.redemption_url"
              outlined
              class="q-mb-md"
            >
              <template v-slot:append>
                <q-btn
                  flat
                  dense
                  icon="content_copy"
                  @click="copyToClipboard(createDialog.result.redemption_url)"
                  aria-label="Copy link to clipboard"
                />
              </template>
            </q-input>

            <div class="row q-mt-lg">
              <q-btn
                unelevated
                color="primary"
                @click="resetCreateDialog"
                label="Create Another"
              />
              <q-btn
                v-close-popup
                flat
                color="grey"
                class="q-ml-auto"
                label="Close Dialog"
              />
            </div>
          </div>
        </q-form>
      </q-card>
    </q-dialog>
  </div>
</template>