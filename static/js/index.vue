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
                  ></q-btn>
                </q-td>
                <q-td v-for="col in props.cols" :key="col.name" :props="props">
                  <span v-if="col.name === 'amount'">{{ col.value }} sats</span>
                  <span v-else-if="col.name === 'status'">
                    <q-badge
                      :color="getStatusColor(col.value)"
                      :label="getStatusText(col.value)"
                    ></q-badge>
                  </span>
                  <span v-else-if="col.name === 'delivery'">
                    <q-badge
                      v-if="props.row.recipient_email"
                      :color="getDeliveryStatusColor(col.value)"
                      :label="getDeliveryStatusText(col.value)"
                    ></q-badge>
                    <span v-else class="text-caption text-grey">&mdash;</span>
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
                          :model-value="props.row.redemption_url"
                          outlined
                          :input-style="{ color: $q.dark.isActive ? '#e0e0e0' : '#333' }"
                        >
                          <template v-slot:append>
                            <q-btn
                              flat
                              dense
                              icon="content_copy"
                              @click="copyToClipboard(props.row.redemption_url)"
                              aria-label="Copy link to clipboard"
                            ></q-btn>
                          </template>
                        </q-input>
                      </div>
                      <div class="col-12">
                        <div class="row q-gutter-sm">
                          <q-btn
                            unelevated
                            dense
                            size="sm"
                            color="primary"
                            icon="mail"
                            @click="openEmailDialog(props.row)"
                            aria-label="Send gift card email"
                          >
                            Send Email
                          </q-btn>
                          <q-btn
                            unelevated
                            dense
                            size="sm"
                            icon="download"
                            :color="$q.dark.isActive ? 'grey-7' : 'grey-5'"
                            @click="downloadPrintable(props.row)"
                            aria-label="Download gift card image"
                          >
                            Download PNG
                          </q-btn>
                        </div>
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
        <q-form @submit="createGiftCard">
          <div v-if="!createDialog.result" class="q-gutter-md">
            <q-select
              filled
              dense
              emit-value
              v-model="createDialog.data.wallet"
              :options="g.user.walletOptions"
              label="Wallet"
            ></q-select>

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
            ></q-input>

            <q-input
              filled
              dense
              v-model.trim="createDialog.data.recipient_name"
              type="text"
              label="Recipient Name"
              hint="Optional — shown on the redemption page."
            ></q-input>

            <q-input
              filled
              dense
              v-model.trim="createDialog.data.sender_name"
              type="text"
              label="Your Name"
              hint="Optional — shown as sender on the redemption page."
            ></q-input>

            <q-input
              filled
              dense
              v-model.trim="createDialog.data.message"
              type="textarea"
              label="Personal Message"
              hint="Optional — shown to recipient."
            ></q-input>

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
            ></q-input>

            <!-- Card Design Section -->
            <q-separator class="q-my-md"></q-separator>
            <h6 class="text-subtitle1 q-my-none">Card Design</h6>

            <div class="row q-col-gutter-md">
              <div class="col-12 col-md-6">
                <q-select
                  filled
                  dense
                  emit-value
                  map-options
                  v-model="selectedTemplate"
                  :options="templateOptions"
                  label="Template"
                  @update:model-value="onTemplateChange"
                ></q-select>
              </div>
              <div class="col-12 col-md-6" v-if="selectedTemplate === 'custom'">
                <q-btn
                  unelevated
                  color="primary"
                  icon="upload"
                  label="Upload Custom Template"
                  :loading="isUploadingTemplate"
                  @click="triggerTemplateUpload"
                ></q-btn>
              </div>
            </div>

            <div class="row q-col-gutter-md q-mt-sm">
              <div class="col-12 col-md-7">
                <div
                  class="card-preview"
                  :style="{width: previewWidth + 'px', height: previewHeight + 'px'}"
                >
                  <img :src="templateUrl" class="template-bg" />
                  <div
                    class="draggable-qr"
                    :style="{left: qrX + 'px', top: qrY + 'px', width: previewQrSize + 'px', height: previewQrSize + 'px'}"
                    @pointerdown="startDrag($event, 'qr')"
                    @pointermove="onDrag"
                    @pointerup="endDrag"
                  >
                    <img
                      src="/giftcards/static/image/qr_placeholder.png"
                      style="width: 100%; height: 100%; object-fit: contain;"
                      @error="$event.target.style.display='none'"
                    />
                    <div
                      class="resize-handle"
                      @pointerdown.stop="startResize"
                      @pointermove="onResize"
                      @pointerup="endResize"
                    ></div>
                  </div>
                  <div
                    v-if="anyTextShown"
                    class="draggable-text"
                    :style="{left: textX + 'px', top: textY + 'px'}"
                    @pointerdown="startDrag($event, 'text')"
                    @pointermove="onDrag"
                    @pointerup="endDrag"
                  >
                    <div :style="previewTextStyle">
                      <div v-if="showAmount">{{ createDialog.data.amount || 0 }} sats</div>
                      <div v-if="showRecipient">For: {{ createDialog.data.recipient_name || 'Recipient' }}</div>
                      <div v-if="showMessage">{{ createDialog.data.message || 'Your message' }}</div>
                    </div>
                  </div>
                </div>
              </div>
              <div class="col-12 col-md-5">
                <div class="q-gutter-sm">
                  <div class="text-caption text-weight-medium">Show on card</div>
                  <q-toggle
                    v-model="showAmount"
                    label="Amount"
                  ></q-toggle>
                  <q-toggle
                    v-model="showRecipient"
                    label="Recipient name"
                  ></q-toggle>
                  <q-toggle
                    v-model="showMessage"
                    label="Message"
                  ></q-toggle>
                  <q-select
                    v-if="anyTextShown"
                    filled
                    dense
                    emit-value
                    map-options
                    v-model="selectedFont"
                    :options="fontOptions"
                    label="Font"
                  ></q-select>
                  <div v-if="anyTextShown" class="text-caption">Font Size: {{ fontSize }}px</div>
                  <q-slider
                    v-if="anyTextShown"
                    v-model="fontSize"
                    :min="12"
                    :max="72"
                    :step="1"
                    label
                  ></q-slider>
                  <q-input
                    v-if="anyTextShown"
                    filled
                    dense
                    v-model="fontColor"
                    type="color"
                    label="Font Color"
                  ></q-input>
                  <div v-if="anyTextShown" class="text-caption">Alignment</div>
                  <q-btn-toggle
                    v-if="anyTextShown"
                    v-model="textAlign"
                    unelevated
                    :options="[
                      {label: 'Left', value: 'left'},
                      {label: 'Center', value: 'center'},
                      {label: 'Right', value: 'right'}
                    ]"
                  ></q-btn-toggle>
                </div>
              </div>
            </div>

            <div class="row q-mt-lg">
              <q-btn
                unelevated
                color="primary"
                type="submit"
                label="Create Gift Card"
                :loading="createDialog.loading"
              ></q-btn>
              <q-btn
                v-close-popup
                flat
                color="grey"
                class="q-ml-auto"
                label="Discard Gift Card"
              ></q-btn>
            </div>
          </div>

          <!-- Success Result -->
          <div v-else class="q-gutter-md">
            <div class="text-center q-mb-lg">
              <h5 class="text-h6 q-my-none text-positive">Gift Card Created</h5>
            </div>

            <q-banner class="q-mb-md bg-warning text-white rounded-borders">
              <template v-slot:avatar>
                <q-icon name="warning"></q-icon>
              </template>
              Save this link — it cannot be recovered.
            </q-banner>

            <q-input
              readonly
              dense
              :model-value="createDialog.result.redemption_url"
              outlined
              class="q-mb-md"
              :input-style="{ color: $q.dark.isActive ? '#e0e0e0' : '#333' }"
            >
              <template v-slot:append>
                <q-btn
                  flat
                  dense
                  icon="content_copy"
                  @click="copyToClipboard(createDialog.result.redemption_url)"
                  aria-label="Copy link to clipboard"
                ></q-btn>
              </template>
            </q-input>

            <div class="row q-mt-lg">
              <q-btn
                unelevated
                color="primary"
                @click="resetCreateDialog"
                label="Create Another"
              ></q-btn>
              <q-btn
                v-close-popup
                flat
                color="grey"
                class="q-ml-auto"
                label="Close Dialog"
              ></q-btn>
            </div>
          </div>
        </q-form>
      </q-card>
    </q-dialog>
    <input
      ref="templateUpload"
      type="file"
      accept="image/png,image/jpeg"
      style="display: none"
      @change="handleTemplateSelected"
    />

    <!-- Email Delivery Dialog -->
    <q-dialog v-model="emailDialog.show" position="top">
      <q-card class="q-pa-lg q-pt-xl lnbits__dialog-card">
        <q-form @submit="sendEmail">
          <div class="q-gutter-md">
            <h6 class="text-subtitle1 q-my-none">Send Gift Card Email</h6>

            <q-input
              filled
              dense
              v-model.trim="emailDialog.data.recipient_email"
              type="email"
              label="Recipient Email"
              :rules="[val => !!val && isValidEmail(val) || 'Enter a valid email address']"
            ></q-input>

            <q-select
              filled
              dense
              emit-value
              map-options
              v-model="emailDialog.data.email_mode"
              :options="emailModeOptions"
              label="Email Mode"
            ></q-select>

            <q-input
              filled
              dense
              v-model.trim="emailDialog.data.subject"
              type="text"
              label="Subject"
              hint="Defaults to 'You have a gift card from {sender}'."
            ></q-input>

            <div v-if="emailDialog.data.email_mode === 'custom'">
              <q-input
                filled
                dense
                v-model.trim="emailDialog.data.body"
                type="textarea"
                label="Email Body"
                hint="Write your personal message to the recipient."
              ></q-input>
            </div>

            <q-separator class="q-my-md"></q-separator>

            <div class="text-caption">Preview:</div>
            <q-card class="q-pa-md bg-grey-2">
              <div class="text-caption text-grey-7">
                Subject: {{ emailDialog.data.subject || 'You have a gift card from ' + (emailDialog.card ? (emailDialog.card.sender_name || 'Anonymous') : 'Anonymous') }}
              </div>
              <div v-if="emailDialog.data.email_mode === 'custom'" class="text-body2 q-mt-sm">
                {{ emailDialog.data.body || '(email body preview)' }}
              </div>
              <div v-else class="q-mt-sm">
                <div style="background: #ffffff; border-radius: 8px; overflow: hidden; box-shadow: 0 1px 4px rgba(0,0,0,0.1);">
                  <div style="background: #1976d2; padding: 16px; text-align: center;">
                    <div style="color: #ffffff; font-size: 22px; font-weight: bold;">
                      {{ emailDialog.card ? emailDialog.card.amount : 0 }} sats
                    </div>
                    <div style="color: #bbdefb; font-size: 12px; margin-top: 4px;">
                      Bitcoin Lightning Gift Card
                    </div>
                  </div>
                  <div style="padding: 16px;">
                    <div style="color: #333; font-size: 14px; margin-bottom: 12px;">
                      <strong>From:</strong> {{ emailDialog.card ? (emailDialog.card.sender_name || 'Anonymous') : 'Anonymous' }}
                    </div>
                    <div v-if="emailDialog.card && emailDialog.card.message" style="background: #f5f5f5; border-left: 4px solid #1976d2; padding: 12px; margin-bottom: 12px;">
                      <div style="color: #555; font-size: 13px;">{{ emailDialog.card.message }}</div>
                    </div>
                    <div style="text-align: center; margin: 16px 0;">
                      <span style="display: inline-block; background: #1976d2; color: #ffffff; padding: 10px 28px; border-radius: 6px; font-size: 14px; font-weight: 600;">
                        Claim Your Gift Card
                      </span>
                    </div>
                  </div>
                </div>
              </div>
            </q-card>

            <div class="row q-mt-lg">
              <q-btn
                unelevated
                color="primary"
                type="submit"
                label="Send Email"
                :loading="emailDialog.loading"
              ></q-btn>
              <q-btn
                v-close-popup
                flat
                dense
                round
                icon="close"
                class="q-ml-auto"
                aria-label="Close email dialog"
              ></q-btn>
            </div>
          </div>
        </q-form>
      </q-card>
    </q-dialog>
  </div>
</template>

<style scoped>
.card-preview {
  position: relative;
  overflow: hidden;
  border: 1px solid rgba(0, 0, 0, 0.12);
  background: #f5f5f5;
  user-select: none;
  touch-action: none;
}

.template-bg {
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  object-fit: fill;
  pointer-events: none;
}

.draggable-qr {
  position: absolute;
  cursor: move;
  touch-action: none;
  border: 1px dashed rgba(0, 0, 0, 0.3);
  background: #ffffff;
}

.draggable-text {
  position: absolute;
  cursor: move;
  touch-action: none;
  max-width: 90%;
  white-space: pre-wrap;
}

.resize-handle {
  position: absolute;
  bottom: 0;
  right: 0;
  width: 12px;
  height: 12px;
  cursor: nwse-resize;
  background: #1976d2;
  border: 1px solid #fff;
  touch-action: none;
}
</style>
