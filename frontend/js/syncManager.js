/**
 * syncManager.js — Enterprise Background Offline-to-Cloud Auto-Sync Engine
 * Manages background store-and-forward sync, online/offline state, and telemetry.
 */

(function () {
  const API_BASE = window.API_BASE || (window.location.origin.includes('http') ? (window.location.origin + '/api') : 'http://127.0.0.1:8000/api');

  function getAuthHeaders() {
    const token = localStorage.getItem('accessToken');
    return token ? { 'Authorization': `Bearer ${token}`, 'Content-Type': 'application/json' } : { 'Content-Type': 'application/json' };
  }

  const SyncManager = {
    isSyncing: false,
    pollInterval: null,
    status: {
      isOnline: navigator.onLine,
      pendingCount: 0,
      totalSyncedCount: 0,
      lastSyncedAt: null,
      cloudSyncUrl: ''
    },

    init: function () {
      window.addEventListener('online', () => {
        this.status.isOnline = true;
        this.updateBadge();
        if (window.showToast) window.showToast('🌐 Internet connection detected. Resuming cloud auto-sync...', 'info', 2500);
        this.pushNow(true);
      });

      window.addEventListener('offline', () => {
        this.status.isOnline = false;
        this.updateBadge();
        if (window.showToast) window.showToast('📡 Offline mode active. All records are safely preserved in local storage.', 'warning', 3000);
      });

      // Periodic check every 60s
      this.pollInterval = setInterval(() => {
        if (navigator.onLine && !this.isSyncing) {
          this.checkStatus(true);
        }
      }, 60000);

      // Initial status check after 2 seconds
      setTimeout(() => {
        this.checkStatus(true);
      }, 2000);
    },

    checkStatus: async function (silent = false) {
      const token = localStorage.getItem('accessToken');
      if (!token) return;

      try {
        const res = await fetch(`${API_BASE}/sync/status`, {
          headers: getAuthHeaders()
        });
        if (res.ok) {
          const data = await res.json();
          this.status.pendingCount = data.pending_count || 0;
          this.status.totalSyncedCount = data.total_synced_count || 0;
          this.status.lastSyncedAt = data.last_synced_at;
          this.status.cloudSyncUrl = data.cloud_sync_url;

          this.updateBadge();
          this.broadcastUpdate(data);

          // If there are pending items and we are online, trigger silent push
          if (this.status.pendingCount > 0 && navigator.onLine && !this.isSyncing) {
            this.pushNow(true);
          }
          return data;
        }
      } catch (err) {
        // Silent catch on offline/network errors
        this.status.isOnline = false;
        this.updateBadge();
      }
    },

    pushNow: async function (silent = false) {
      if (this.isSyncing) return;
      const token = localStorage.getItem('accessToken');
      if (!token) return;

      this.isSyncing = true;
      this.updateBadge(true);

      try {
        const res = await fetch(`${API_BASE}/sync/push`, {
          method: 'POST',
          headers: getAuthHeaders()
        });

        const data = await res.json();
        if (res.ok) {
          if (data.synced_count > 0 && !silent && window.showToast) {
            window.showToast(`☁️ Cloud Auto-Sync: Successfully synchronized ${data.synced_count} delta records.`, 'success');
          }
          await this.checkStatus(true);
          return data;
        } else {
          if (!silent && window.showToast) {
            window.showToast(`Sync Notice: ${data.detail || 'Sync failed.'}`, 'warning');
          }
        }
      } catch (err) {
        if (!silent && window.showToast) {
          window.showToast(`Sync skipped: working in offline local mode.`, 'info');
        }
      } finally {
        this.isSyncing = false;
        this.updateBadge(false);
      }
    },

    pullSnapshot: async function () {
      try {
        const res = await fetch(`${API_BASE}/sync/pull-snapshot`, {
          method: 'POST',
          headers: getAuthHeaders()
        });
        if (res.ok) {
          const data = await res.json();
          return data.snapshot;
        } else {
          const err = await res.json();
          throw new Error(err.detail || 'Snapshot pull failed.');
        }
      } catch (e) {
        throw e;
      }
    },

    updateBadge: function (syncingOverride = null) {
      let badge = document.getElementById('topbarSyncBadge');
      const topbar = document.querySelector('.topbar');
      if (!topbar) return;

      if (!badge) {
        badge = document.createElement('div');
        badge.id = 'topbarSyncBadge';
        badge.className = 'topbar-sync-badge';
        badge.style.cssText = 'display:inline-flex; align-items:center; gap:6px; font-size:0.75rem; font-weight:700; padding:4px 10px; border-radius:999px; margin-left:10px; cursor:pointer; transition:all 0.2s ease;';
        badge.title = 'Click to force cloud synchronization';
        badge.addEventListener('click', () => {
          this.pushNow(false);
        });

        // Insert before user controls or append to first topbar child
        const rightContainer = topbar.querySelector('.topbar-user, .user-profile, [style*="margin-left:auto"]') || topbar;
        if (rightContainer && rightContainer !== topbar) {
          rightContainer.prepend(badge);
        } else {
          topbar.appendChild(badge);
        }
      }

      const isSyncing = syncingOverride !== null ? syncingOverride : this.isSyncing;
      const isOnline = navigator.onLine;

      if (isSyncing) {
        badge.innerHTML = `<span style="display:inline-block; animation:spin 1s linear infinite;">🔄</span> <span>Syncing...</span>`;
        badge.style.background = 'rgba(59, 130, 246, 0.15)';
        badge.style.color = '#3b82f6';
        badge.style.border = '1px solid rgba(59, 130, 246, 0.3)';
      } else if (!isOnline) {
        badge.innerHTML = `<span>🟡</span> <span>Offline (Local)</span>`;
        badge.style.background = 'rgba(245, 158, 11, 0.15)';
        badge.style.color = '#f59e0b';
        badge.style.border = '1px solid rgba(245, 158, 11, 0.3)';
        badge.title = 'Offline mode active. All records are stored locally.';
      } else if (this.status.pendingCount > 0) {
        badge.innerHTML = `<span>🔄</span> <span>Pending (${this.status.pendingCount})</span>`;
        badge.style.background = 'rgba(234, 88, 12, 0.15)';
        badge.style.color = '#ea580c';
        badge.style.border = '1px solid rgba(234, 88, 12, 0.3)';
        badge.title = `${this.status.pendingCount} local changes pending cloud sync. Click to push now.`;
      } else {
        badge.innerHTML = `<span>🟢</span> <span>Cloud Synced</span>`;
        badge.style.background = 'rgba(16, 185, 129, 0.15)';
        badge.style.color = '#10b981';
        badge.style.border = '1px solid rgba(16, 185, 129, 0.3)';
        badge.title = `All records synchronized with cloud.${this.status.lastSyncedAt ? ' Last sync: ' + new Date(this.status.lastSyncedAt).toLocaleTimeString() : ''}`;
      }
    },

    broadcastUpdate: function (data) {
      window.dispatchEvent(new CustomEvent('sms:sync-updated', { detail: data }));
    }
  };

  window.SyncManager = SyncManager;

  document.addEventListener('DOMContentLoaded', () => {
    SyncManager.init();
  });
})();
