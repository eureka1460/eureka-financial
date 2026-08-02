const https = require('https');
const http = require('http');

// 后端地址：优先读环境变量，fallback 到硬编码
const BACKEND_URL =
  process.env.BACKEND_URL ||
  'https://eurekabackend-290702-8-1462314987.sh.run.tcloudbase.com';

/**
 * API 代理云函数
 * 用 Node.js 原生 https 模块转发请求到 Python 后端
 *
 * event = { method, path, data, params, headers }
 */
exports.main = async (event, context) => {
  // 输入校验
  if (!event || typeof event !== 'object') {
    return { code: 400, message: '请求参数无效', data: null };
  }

  const { method = 'GET', path = '/', data = null, params = null, headers: userHeaders = {} } = event;

  // 构建 URL path
  let urlPath = '/' + String(path).replace(/^\/+/, '');
  if (params && typeof params === 'object') {
    const qs = Object.entries(params)
      .filter(([, v]) => v !== undefined && v !== null && v !== '')
      .map(([k, v]) => `${encodeURIComponent(k)}=${encodeURIComponent(v)}`)
      .join('&');
    if (qs) urlPath += '?' + qs;
  }

  // 解析后端地址
  let parsed;
  try {
    parsed = new URL(BACKEND_URL);
  } catch (e) {
    return { code: 500, message: '后端地址配置错误', data: null };
  }

  const isHttps = parsed.protocol === 'https:';

  const options = {
    hostname: parsed.hostname,
    port: parsed.port || (isHttps ? 443 : 80),
    path: urlPath,
    method: method,
    headers: Object.assign(
      { 'Content-Type': 'application/json' },
      userHeaders
    ),
    timeout: 30000,
  };

  // 执行请求
  return new Promise((resolve, reject) => {
    let settled = false;

    function settle(result) {
      if (!settled) {
        settled = true;
        resolve(result);
      }
    }

    try {
      const transport = isHttps ? https : http;

      const req = transport.request(options, (res) => {
        let body = '';
        res.on('data', (chunk) => { body += chunk; });
        res.on('end', () => {
          try {
            const response = JSON.parse(body);
            settle({
              code: response.code ?? 200,
              message: response.message || 'ok',
              data: response.data !== undefined ? response.data : response,
            });
          } catch (e) {
            console.error('JSON 解析失败，原始响应:', body.substring(0, 500));
            settle({ code: 502, message: '响应格式错误', data: null });
          }
        });
        res.on('error', (err) => {
          console.error('响应流错误:', err.message);
          settle({ code: 502, message: '响应传输中断', data: null });
        });
      });

      req.on('error', (err) => {
        console.error('API Proxy Error:', err.message);
        settle({ code: 502, message: '后端服务暂不可用', data: null });
      });

      req.on('timeout', () => {
        req.destroy();
        settle({ code: 502, message: '请求超时', data: null });
      });

      if (method !== 'GET' && data) {
        try {
          req.write(JSON.stringify(data));
        } catch (e) {
          settle({ code: 502, message: '请求发送失败', data: null });
          return;
        }
      }

      req.end();
    } catch (err) {
      console.error('请求构造错误:', err.message);
      settle({ code: 500, message: '请求构造失败', data: null });
    }
  });
};
