const express = require('express');
const puppeteer = require('puppeteer');
const bodyParser = require('body-parser');

const app = express();
const PORT = process.env.PORT || 3000;

app.use(bodyParser.json());

app.get('/', (req, res) => {
  res.send('🚀 FlareSolverr Clone is Running');
});

app.post('/v1', async (req, res) => {
  const {
    cmd,
    url,
    headers = {},
    cookies = [],
    userAgent,
    postData,
    method = 'GET',
    maxTimeout = 20000,
  } = req.body;

  if (!url || !cmd || !['request.get', 'request.post'].includes(cmd)) {
    return res.status(400).json({ status: 'error', message: 'Invalid command or missing URL' });
  }

  let browser;
  try {
    browser = await puppeteer.launch({
      headless: true,
      args: ['--no-sandbox', '--disable-setuid-sandbox'],
    });

    const page = await browser.newPage();

    if (userAgent) {
      await page.setUserAgent(userAgent);
    }

    if (headers && Object.keys(headers).length > 0) {
      await page.setExtraHTTPHeaders(headers);
    }

    if (cookies.length > 0) {
      await page.setCookie(...cookies);
    }

    let response, body;

    if (cmd === 'request.get') {
      response = await page.goto(url, {
        waitUntil: 'networkidle2',
        timeout: maxTimeout,
      });
      body = await page.content();

    } else if (cmd === 'request.post') {
      await page.goto('about:blank'); // initialize page context
      const result = await page.evaluate(
        async ({ url, headers, body }) => {
          const res = await fetch(url, {
            method: 'POST',
            headers,
            body,
          });
          const text = await res.text();
          return {
            status: res.status,
            headers: Object.fromEntries(res.headers.entries()),
            body: text,
          };
        },
        {
          url,
          headers,
          body: postData || '',
        }
      );
      response = {
        status: () => result.status,
        headers: () => result.headers,
      };
      body = result.body;
    }

    const status = response.status();
    const responseHeaders = response.headers();

    await browser.close();

    return res.json({
      status: 'ok',
      solution: {
        url,
        status,
        headers: responseHeaders,
        response: body,
      },
    });
  } catch (err) {
    if (browser) await browser.close();
    console.error('Error:', err.message);
    res.status(500).json({ status: 'error', message: err.message });
  }
});

app.listen(PORT, () => {
  console.log(`✅ FlareSolverr Clone ready at http://localhost:${PORT}`);
});
