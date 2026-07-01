import { createStore } from "/js/AlpineStore.js";
import { store as navStore } from "/components/chat/navigation/chat-navigation-store.js";
import * as api from "/js/api.js";
import {
  toastFrontendInfo,
  NotificationPriority,
} from "/components/notifications/notification-store.js";
import { sleep } from "/js/sleep.js";
import { store as chatsStore } from "/components/sidebar/chats/chats-store.js";

const model = {
  // items: [],
  get items() {
    return chatsStore.selectedContext?.message_queue || [];
  },

  pendingItems: [], // Local pending items (uploading to queue)

  _pendingAddOps: {},

  _lastAddToQueuePromise: Promise.resolve(),

  _getQueueScrollerEl() {
    return document.querySelector(".queue-preview .queue-items");
  },

  scrollQueueToBottom() {
    const el = this._getQueueScrollerEl();
    if (!el) return;

    const scroll = () => {
      el.scrollTop = el.scrollHeight;
    };

    requestAnimationFrame(() => {
      scroll();
      requestAnimationFrame(scroll);
    });
  },

  get hasQueue() {
    return this.items.length > 0 || this.pendingItems.length > 0;
  },

  get count() {
    return this.items.length + this.pendingItems.length;
  },

  // Combined items for display: confirmed first, then pending at the end
  get allItems() {
    return [...this.items, ...this.pendingItems];
  },

  // chat_project_filter_queue_edit_patch
  editingItem: null,
  editText: "",
  editSaving: false,
  _editingAttachments: [],
  _finishEditPromise: null,

  isEditing(item) {
    return !!item && !!this.editingItem && this.editingItem.id === item.id;
  },

  editItem(item) {
    if (!item || item.pending) return;
    this.editingItem = { ...item };
    this.editText = item.text || "";
    this._editingAttachments = [...(item.attachments || [])];
    const chatInput = globalThis.Alpine?.store?.("chatInput");
    if (chatInput) {
      chatInput.message = this.editText;
      queueMicrotask(() => chatInput.adjustTextareaHeight?.());
    }
    queueMicrotask(() => {
      const input = document.getElementById("chat-input");
      if (input) {
        input.focus();
        input.selectionStart = input.selectionEnd = input.value.length;
      }
    });
  },

  cancelEdit() {
    if (this.editSaving) return false;
    this.editingItem = null;
    this.editText = "";
    this.editSaving = false;
    this._editingAttachments = [];
    return true;
  },

  async finishEdit() {
    if (this._finishEditPromise) return this._finishEditPromise;
    const item = this.editingItem;
    if (!item || item.pending) return false;
    const context = globalThis.getContext?.();
    if (!context) return false;

    const text = this.editText ?? "";
    const attachments = [...(this._editingAttachments || [])];
    const itemId = item.id;

    const run = async () => {
      this.editSaving = true;
      try {
        await api.callJsonApi("/message_queue_remove", { context, item_id: itemId });
        const resp = await api.fetchApi("/message_queue_add", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          credentials: "same-origin",
          body: JSON.stringify({ context, text, attachments, item_id: itemId }),
        });
        const result = await this.parseQueueJsonResponse(resp, "message_queue_edit");
        if (!result?.ok) return false;
        this.editingItem = null;
        this.editText = "";
        this._editingAttachments = [];
        return true;
      } catch (e) {
        console.error("Failed to edit queued message:", e);
        return false;
      } finally {
        this.editSaving = false;
        this._finishEditPromise = null;
      }
    };

    this._finishEditPromise = run();
    return this._finishEditPromise;
  },

  async parseQueueJsonResponse(resp, label = "queue request") {
    // chat_project_filter_queue_edit_patch_v2
    if (!resp) throw new Error(`${label} did not return a response`);
    const contentType = resp.headers?.get?.("content-type") || "";
    const bodyText = await resp.text();
    if (!resp.ok) {
      const detail = bodyText ? bodyText.slice(0, 300) : resp.statusText;
      throw new Error(`${label} failed (${resp.status}): ${detail}`);
    }
    if (!contentType.toLowerCase().includes("application/json")) {
      const preview = bodyText ? bodyText.slice(0, 300) : "empty response";
      throw new Error(`${label} returned non-JSON response: ${preview}`);
    }
    try {
      return bodyText ? JSON.parse(bodyText) : {};
    } catch (e) {
      throw new Error(`${label} returned invalid JSON: ${e?.message || e}`);
    }
  },

  async addToQueue(text, attachments = []) {
    const context = globalThis.getContext?.();
    if (!context) return false;

    // Generate a temporary ID for pending item
    const tempId = `${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;
    const pendingItem = {
      id: tempId,
      text: text || "(attachment only)",
      attachments: attachments.map((a) => a.name || a.file?.name || "file"),
      pending: true,
    };

    const controller =
      typeof AbortController !== "undefined" ? new AbortController() : null;
    this._pendingAddOps = {
      ...this._pendingAddOps,
      [tempId]: {
        canceled: false,
        controller,
      },
    };

    // Add to pending immediately for UI feedback
    this.pendingItems = [...this.pendingItems, pendingItem];
    this.scrollQueueToBottom();

    const run = async () => {
      const op = this._pendingAddOps?.[tempId];
      if (!op || op.canceled) {
        this._pendingAddOps = { ...this._pendingAddOps };
        delete this._pendingAddOps[tempId];
        return false;
      }

      try {
        let filenames = [];
        if (attachments.length > 0) {
          const formData = new FormData();
          for (const att of attachments) {
            formData.append("file", att.file || att);
          }
          const resp = await api.fetchApi("/upload", {
            method: "POST",
            body: formData,
            signal: op.controller ? op.controller.signal : undefined,
          });
          const result = await this.parseQueueJsonResponse(resp, "upload");
          filenames = result.filenames || [];
        }

        const resp = await api.fetchApi("/message_queue_add", {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
          credentials: "same-origin",
          body: JSON.stringify({
            context,
            text,
            attachments: filenames,
            item_id: tempId,
          }),
          signal: op.controller ? op.controller.signal : undefined,
        });

        const response = await this.parseQueueJsonResponse(resp, "message_queue_add");

        return response?.ok || false;
      } catch (e) {
        if (e?.name !== "AbortError") {
          console.error("Failed to queue message:", e);
        }
        return false;
      } finally {
        this._pendingAddOps = { ...this._pendingAddOps };
        delete this._pendingAddOps[tempId];
      }
    };

    // Chain promises to ensure sequential execution
    const previous = this._lastAddToQueuePromise || Promise.resolve();
    const chained = previous.catch(() => false).then(run);
    this._lastAddToQueuePromise = chained.catch(() => false);
    return await chained;
  },

  async removeItem(itemId) {
    const context = globalThis.getContext?.();
    if (!context) return;

    const isPending = this.pendingItems.some((p) => p.id === itemId);
    if (isPending) {
      const op = this._pendingAddOps?.[itemId];
      if (op) {
        op.canceled = true;
        if (op.controller) {
          op.controller.abort();
        }
      }
      this.pendingItems = this.pendingItems.filter((p) => p.id !== itemId);
      return;
    }

    try {
      await api.callJsonApi("/message_queue_remove", {
        context,
        item_id: itemId,
      });
    } catch (e) {
      console.error("Failed to remove from queue:", e);
    }
  },

  async clearQueue() {
    const context = globalThis.getContext?.();
    if (!context) return;
    try {
      await api.callJsonApi("/message_queue_remove", { context });
    } catch (e) {
      console.error("Failed to clear queue:", e);
    }
  },

  async sendItem(itemId) {
    const context = globalThis.getContext?.();
    if (!context) return;
    try {
      await api.callJsonApi("/message_queue_send", {
        context,
        item_id: itemId,
      });
    } catch (e) {
      console.error("Failed to send queued message:", e);
    }
  },

  async sendAll() {
    const context = globalThis.getContext?.();
    if (!context || !this.hasQueue) return;

    // check for pending uploads and notify user
    if (this.pendingItems.length > 0) {
      await sleep(1000);
      if (this.pendingItems.length > 0) {
        toastFrontendInfo(
          "There are pending uploads in the queue. You can wait for them to finish or remove them.",
          "Pending uploads",
          3,
          "pending-uploads",
          NotificationPriority.NORMAL,
          true,
        );
        return;
      }
    }

    if (!this.hasQueue) return;
    try {
      navStore.scrollToBottom();
      await api.callJsonApi("/message_queue_send", { context, send_all: true });
    } catch (e) {
      console.error("Failed to send all queued:", e);
    }
  },

  updateFromPoll() {
    // this.items = queue || [];

    if (this.pendingItems.length > 0) {
      const serverIds = new Set(this.items.map((i) => i.id).filter(Boolean));
      this.pendingItems = this.pendingItems.filter((p) => {
        if (!p.id) return true;
        return !serverIds.has(p.id);
      });
    }
    // this.scrollQueueToBottom();
  },

  getAttachmentUrl(filename) {
    return `/api/image_get?path=/a0/usr/uploads/${encodeURIComponent(filename)}`;
  },
};

const store = createStore("messageQueue", model);
export { store };
