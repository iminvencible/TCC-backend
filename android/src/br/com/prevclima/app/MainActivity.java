package br.com.prevclima.app;

import android.Manifest;
import android.app.Activity;
import android.content.Intent;
import android.content.pm.PackageManager;
import android.graphics.Color;
import android.net.Uri;
import android.os.Bundle;
import android.view.Gravity;
import android.view.View;
import android.webkit.CookieManager;
import android.webkit.GeolocationPermissions;
import android.webkit.WebChromeClient;
import android.webkit.WebResourceError;
import android.webkit.WebResourceRequest;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import android.widget.Button;
import android.widget.LinearLayout;
import android.widget.ProgressBar;
import android.widget.TextView;

/** USER-only mobile client. Authorization remains enforced by the server. */
public final class MainActivity extends Activity {
    private static final String HOST = "home.tailf3e991.ts.net";
    private static final String HOME = "https://" + HOST + "/mobile/";
    private static final int LOCATION_PERMISSION = 10;
    private WebView web;
    private LinearLayout errorPanel;
    private ProgressBar progress;
    private String lastPage = HOME;
    private String locationOrigin;
    private GeolocationPermissions.Callback locationCallback;

    private boolean trusted(Uri uri) {
        return "https".equals(uri.getScheme()) && HOST.equals(uri.getHost())
            && (uri.getPort() == -1 || uri.getPort() == 443) && uri.getUserInfo() == null;
    }

    private boolean mobilePage(Uri uri) {
        if (!trusted(uri)) return false;
        String path = uri.getPath();
        return path != null && (path.equals("/mobile") || path.startsWith("/mobile/"));
    }

    @Override public void onCreate(Bundle state) {
        super.onCreate(state);
        LinearLayout root = new LinearLayout(this);
        root.setOrientation(LinearLayout.VERTICAL);
        root.setBackgroundColor(Color.rgb(8, 15, 26));
        root.setFitsSystemWindows(true);
        progress = new ProgressBar(this, null, android.R.attr.progressBarStyleHorizontal);
        root.addView(progress, new LinearLayout.LayoutParams(-1, 5));
        errorPanel = new LinearLayout(this);
        errorPanel.setOrientation(LinearLayout.VERTICAL);
        errorPanel.setGravity(Gravity.CENTER);
        errorPanel.setPadding(32, 32, 32, 32);
        TextView message = new TextView(this);
        message.setText("Não foi possível conectar ao PrevClima.\nConfira sua internet e tente novamente.\n\nO aplicativo precisa de conexão para atualizar previsões e avisos.");
        message.setTextColor(Color.WHITE);
        message.setTextSize(18);
        message.setGravity(Gravity.CENTER);
        errorPanel.addView(message);
        Button retry = new Button(this);
        retry.setText("Tentar novamente");
        retry.setOnClickListener(new View.OnClickListener() {
            @Override public void onClick(View view) { load(lastPage); }
        });
        errorPanel.addView(retry);
        errorPanel.setVisibility(View.GONE);
        root.addView(errorPanel, new LinearLayout.LayoutParams(-1, -1));
        web = new WebView(this);
        web.setBackgroundColor(Color.rgb(8, 15, 26));
        root.addView(web, new LinearLayout.LayoutParams(-1, 0, 1));
        setContentView(root);
        WebSettings settings = web.getSettings();
        settings.setJavaScriptEnabled(true);
        settings.setDomStorageEnabled(true);
        settings.setAllowFileAccess(false);
        settings.setAllowContentAccess(false);
        settings.setMixedContentMode(WebSettings.MIXED_CONTENT_NEVER_ALLOW);
        settings.setGeolocationEnabled(true);
        settings.setMediaPlaybackRequiresUserGesture(true);
        settings.setSafeBrowsingEnabled(true);
        settings.setUserAgentString(settings.getUserAgentString() + " PrevClimaAndroid/1.0");
        CookieManager.getInstance().setAcceptCookie(true);
        CookieManager.getInstance().setAcceptThirdPartyCookies(web, false);
        WebView.setWebContentsDebuggingEnabled(false);
        web.setWebViewClient(new WebViewClient() {
            @Override public void onPageStarted(WebView view, String url, android.graphics.Bitmap favicon) {
                if (!mobilePage(Uri.parse(url))) { view.stopLoading(); load(HOME); }
            }
            @Override public boolean shouldOverrideUrlLoading(WebView view, WebResourceRequest request) {
                if (!request.isForMainFrame()) return !trusted(request.getUrl());
                Uri uri = request.getUrl();
                if (mobilePage(uri)) return false;
                // Shared verification/reset endpoints may redirect here on older servers.
                if (trusted(uri) && "/conta.html".equals(uri.getPath())) {
                    load("https://" + HOST + "/mobile/conta.html" + (uri.getEncodedFragment() == null ? "" : "#" + uri.getEncodedFragment()));
                } else if ("https".equals(uri.getScheme())) {
                    try { startActivity(new Intent(Intent.ACTION_VIEW, uri)); }
                    catch (android.content.ActivityNotFoundException ignored) { }
                }
                return true;
            }
            @Override public void onPageFinished(WebView view, String url) {
                if (mobilePage(Uri.parse(url))) lastPage = url;
                CookieManager.getInstance().flush();
            }
            @Override public void onReceivedError(WebView view, WebResourceRequest request, WebResourceError error) {
                if (request.isForMainFrame()) showError();
            }
            @Override public void onReceivedHttpError(WebView view, WebResourceRequest request, android.webkit.WebResourceResponse response) {
                if (request.isForMainFrame() && response.getStatusCode() >= 400) showError();
            }
            // SSL errors use WebView's default cancel behavior; there is no bypass.
        });
        web.setWebChromeClient(new WebChromeClient() {
            @Override public void onProgressChanged(WebView view, int value) {
                progress.setProgress(value);
                progress.setVisibility(value == 100 ? View.GONE : View.VISIBLE);
            }
            @Override public void onGeolocationPermissionsShowPrompt(String origin, GeolocationPermissions.Callback callback) {
                if (!trusted(Uri.parse(origin))) { callback.invoke(origin, false, false); return; }
                if (checkSelfPermission(Manifest.permission.ACCESS_COARSE_LOCATION) == PackageManager.PERMISSION_GRANTED) {
                    callback.invoke(origin, true, false); return;
                }
                if (locationCallback != null) locationCallback.invoke(locationOrigin, false, false);
                locationOrigin = origin;
                locationCallback = callback;
                requestPermissions(new String[] {Manifest.permission.ACCESS_FINE_LOCATION, Manifest.permission.ACCESS_COARSE_LOCATION}, LOCATION_PERMISSION);
            }
        });
        if (state == null || web.restoreState(state) == null) load(HOME);
    }

    private void load(String url) {
        if (!mobilePage(Uri.parse(url))) url = HOME;
        errorPanel.setVisibility(View.GONE);
        web.setVisibility(View.VISIBLE);
        lastPage = url;
        web.loadUrl(url);
    }
    private void showError() {
        web.setVisibility(View.GONE);
        progress.setVisibility(View.GONE);
        errorPanel.setVisibility(View.VISIBLE);
    }
    @Override public void onRequestPermissionsResult(int request, String[] permissions, int[] grants) {
        super.onRequestPermissionsResult(request, permissions, grants);
        if (request == LOCATION_PERMISSION && locationCallback != null) {
            boolean allowed = checkSelfPermission(Manifest.permission.ACCESS_COARSE_LOCATION) == PackageManager.PERMISSION_GRANTED;
            locationCallback.invoke(locationOrigin, allowed, false);
            locationCallback = null;
        }
    }
    @Override public void onBackPressed() {
        if (web.canGoBack()) web.goBack(); else super.onBackPressed();
    }
    @Override protected void onSaveInstanceState(Bundle state) {
        web.saveState(state);
        super.onSaveInstanceState(state);
    }
    @Override protected void onPause() { web.onPause(); super.onPause(); }
    @Override protected void onResume() { super.onResume(); web.onResume(); }
    @Override protected void onDestroy() {
        if (locationCallback != null) locationCallback.invoke(locationOrigin, false, false);
        web.destroy();
        super.onDestroy();
    }
}
