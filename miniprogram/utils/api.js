/**
 * 统一 API 调用模块
 *
 * 所有请求通过云函数 apiProxy 转发到 Python 后端。
 * 返回格式：{ code: 200, message: "ok", data: ... }
 */

const CLOUD_FUNCTION_NAME = 'apiProxy';

/** 基础请求 */
function request(method, path, data = null, params = null) {
  return wx.cloud
    .callFunction({
      name: CLOUD_FUNCTION_NAME,
      data: { method, path, data, params },
    })
    .then((res) => {
      const body = res.result;
      if (body && body.code >= 200 && body.code < 300) {
        return body;
      }
      throw body || { code: 500, message: '未知错误' };
    });
}

/** GET 请求 */
function get(path, params = null) {
  return request('GET', path, null, params);
}

/** POST 请求 */
function post(path, data = {}) {
  return request('POST', path, data, null);
}

// ── 业务 API ──────────────────────────────────────────────

/** 获取股票列表 */
function getStocks(params = {}) {
  return get('/api/v1/stocks', params);
}

/** 获取股票详情 */
function getStockDetail(symbol) {
  return get(`/api/v1/stocks/${symbol}`);
}

/** 获取财务历史 */
function getFinancials(symbol, params = {}) {
  return get(`/api/v1/stocks/${symbol}/financials`, params);
}

/** 获取指标列表 */
function getIndicators() {
  return get('/api/v1/indicators');
}

/** 触发数据同步 */
function triggerSync(data = {}) {
  return post('/api/v1/data/sync', data);
}

/** 获取同步状态 */
function getSyncStatus() {
  return get('/api/v1/data/sync/status');
}

/** 选股筛选 */
function searchScreener(data = {}) {
  return post('/api/v1/screener/search', data);
}

/** DCF 估值 */
function calcDCF(data = {}) {
  return post('/api/v1/valuation/dcf', data);
}

/** DDM 估值 */
function calcDDM(data = {}) {
  return post('/api/v1/valuation/ddm', data);
}

module.exports = {
  request,
  get,
  post,
  getStocks,
  getStockDetail,
  getFinancials,
  getIndicators,
  triggerSync,
  getSyncStatus,
  searchScreener,
  calcDCF,
  calcDDM,
};
