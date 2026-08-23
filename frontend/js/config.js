/* ================================================================
   config.js — Global SMS Environment & Centralized API Client
   ================================================================ */
(function() {
  'use strict';
  
  // Dynamic API resolution based on current host/origin
  window.API_BASE = (typeof window !== 'undefined' && window.location && window.location.origin && window.location.origin.includes('http')) 
    ? (window.location.origin + '/api') 
    : 'http://127.0.0.1:8000/api';

  // Global Toast Notification Helper
  window.showToast = function(message, type = 'info') {
    if (!document.body) return;
    const existing = document.getElementById('sms-global-toast');
    if (existing) existing.remove();

    const colors = {
      success: '#10b981',
      error: '#ef4444',
      warning: '#f59e0b',
      info: '#3b82f6'
    };

    const toast = document.createElement('div');
    toast.id = 'sms-global-toast';
    toast.style.cssText = `position:fixed; bottom:24px; right:24px; z-index:99999; background:${colors[type] || colors.info}; color:#ffffff; padding:12px 20px; border-radius:10px; font-family:sans-serif; font-size:0.9rem; font-weight:600; box-shadow:0 10px 25px rgba(0,0,0,0.35); display:flex; align-items:center; gap:12px; animation: fadeIn 0.3s ease; max-width:400px;`;
    toast.innerHTML = `<span>${message}</span><button onclick="this.parentElement.remove()" style="background:none; border:none; color:#fff; font-size:1.2rem; cursor:pointer; line-height:1;">×</button>`;
    document.body.appendChild(toast);
    setTimeout(() => { if (toast.parentElement) toast.remove(); }, 5000);
  };

  // Centralized API Client Wrapper
  window.fetchAPI = async function(endpoint, options = {}) {
    const token = localStorage.getItem('accessToken');
    const headers = Object.assign({}, options.headers || {});

    if (token && !headers['Authorization']) {
      headers['Authorization'] = 'Bearer ' + token;
    }

    let body = options.body;
    if (body && typeof body === 'object' && !(body instanceof FormData)) {
      headers['Content-Type'] = 'application/json';
      body = JSON.stringify(body);
    }

    const url = endpoint.startsWith('http') 
      ? endpoint 
      : (window.API_BASE + (endpoint.startsWith('/') ? endpoint : '/' + endpoint));

    try {
      const response = await fetch(url, { ...options, headers, body });

      if (response.status === 401) {
        localStorage.removeItem('accessToken');
        localStorage.removeItem('userRole');
        localStorage.removeItem('username');
        localStorage.removeItem('userId');

        if (!window.location.pathname.includes('auth.html')) {
          window.location.href = 'auth.html?msg=' + encodeURIComponent('Session expired. Please log in again.');
        }
        throw new Error('Unauthorized');
      }

      let data;
      const contentType = response.headers.get('content-type') || '';
      if (contentType.includes('application/json')) {
        data = await response.json();
      } else {
        data = await response.text();
      }

      if (!response.ok) {
        const errorMsg = (data && data.detail) 
          ? (typeof data.detail === 'string' ? data.detail : JSON.stringify(data.detail)) 
          : (typeof data === 'string' ? data : 'Request failed with status ' + response.status);
        throw new Error(errorMsg);
      }

      return data;
    } catch (err) {
      if (err.message !== 'Unauthorized') {
        console.error('API Error [' + endpoint + ']:', err.message);
      }
      throw err;
    }
  };

  // Render Animated Skeleton Shimmer Table Rows
  window.renderSkeletonRows = function(tbodyId, colCount = 6, rowCount = 5) {
    const tbody = document.getElementById(tbodyId);
    if (!tbody) return;

    let rowsHtml = '';
    for (let r = 0; r < rowCount; r++) {
      let cellsHtml = '';
      for (let c = 0; c < colCount; c++) {
        const randomWidth = Math.floor(Math.random() * 40) + 50;
        cellsHtml += `<td><span class="skeleton-box" style="width:${randomWidth}%;"></span></td>`;
      }
      rowsHtml += `<tr>${cellsHtml}</tr>`;
    }
    tbody.innerHTML = rowsHtml;
  };

  // Animated Button Loading Spinner Controller
  window.setButtonLoading = function(buttonOrId, isLoading, loadingText = 'Processing...') {
    const btn = typeof buttonOrId === 'string' ? document.getElementById(buttonOrId) : buttonOrId;
    if (!btn) return;

    if (isLoading) {
      if (!btn.dataset.origContent) {
        btn.dataset.origContent = btn.innerHTML;
      }
      btn.disabled = true;
      btn.classList.add('btn-loading');
      btn.innerHTML = `<span class="btn-spinner"></span> ${loadingText}`;
    } else {
      btn.disabled = false;
      btn.classList.remove('btn-loading');
      if (btn.dataset.origContent) {
        btn.innerHTML = btn.dataset.origContent;
        delete btn.dataset.origContent;
      }
    }
  };

  // Global network error listener to display friendly toast when server is unreachable
  window.addEventListener('unhandledrejection', function(event) {
    if (event.reason && (event.reason.name === 'TypeError' || (event.reason.message && event.reason.message.includes('fetch')))) {
      console.warn('Network request failed:', event.reason);
      window.showToast('⚠️ Local server unreachable. Please check connection.', 'error');
    }
  });
})();


