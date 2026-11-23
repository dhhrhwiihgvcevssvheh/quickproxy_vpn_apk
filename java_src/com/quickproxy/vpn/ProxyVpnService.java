package com.quickproxy.vpn;

import android.app.Notification;
import android.app.NotificationChannel;
import android.app.NotificationManager;
import android.content.Intent;
import android.net.VpnService;
import android.os.Build;
import android.os.ParcelFileDescriptor;

public class ProxyVpnService extends VpnService {
    private static final String CHANNEL_ID = "quickproxy_vpn_channel";
    private static final int NOTIFICATION_ID = 101;

    private ParcelFileDescriptor vpnInterface = null;
    private Thread vpnThread = null;
    private volatile boolean running = false;

    @Override
    public void onCreate() {
        super.onCreate();
        createNotificationChannel();
    }

    private void createNotificationChannel() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            NotificationChannel channel = new NotificationChannel(
                CHANNEL_ID,
                "QuickProxy VPN Service",
                NotificationManager.IMPORTANCE_LOW
            );
            NotificationManager manager = getSystemService(NotificationManager.class);
            if (manager != null) {
                manager.createNotificationChannel(channel);
            }
        }
    }

    private Notification buildNotification(String text) {
        Notification.Builder builder = (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O)
            ? new Notification.Builder(this, CHANNEL_ID)
            : new Notification.Builder(this);

        builder.setContentTitle("QuickProxy Device VPN")
               .setContentText(text)
               .setSmallIcon(android.R.drawable.ic_lock_idle_lock);

        return builder.build();
    }

    @Override
    public int onStartCommand(Intent intent, int flags, int startId) {
        if (intent == null) {
            return START_NOT_STICKY;
        }

        String action = intent.getAction();
        if ("STOP".equals(action)) {
            stopVpnSession();
            stopForeground(true);
            stopSelf();
            return START_NOT_STICKY;
        }

        String protocol = intent.getStringExtra("protocol");
        String host = intent.getStringExtra("host");
        int port = intent.getIntExtra("port", 1080);
        String username = intent.getStringExtra("username");
        String password = intent.getStringExtra("password");

        startForeground(NOTIFICATION_ID, buildNotification("Connecting: " + protocol + " " + host + ":" + port));
        startVpnSession(protocol, host, port, username, password);
        return START_STICKY;
    }

    private void startVpnSession(String protocol, String host, int port, String username, String password) {
        stopVpnSession();
        running = true;

        vpnThread = new Thread(() -> {
            try {
                Builder builder = new Builder();
                builder.setSession("QuickProxyVPN")
                       .addAddress("10.0.0.2", 32)
                       .addRoute("0.0.0.0", 0)
                       .setMtu(1500);

                try {
                    builder.addDisallowedApplication(getPackageName());
                } catch (Exception ignored) {
                }

                vpnInterface = builder.establish();
                if (vpnInterface == null) {
                    running = false;
                    return;
                }

                while (running && !Thread.currentThread().isInterrupted()) {
                    Thread.sleep(1000);
                }
            } catch (Exception ignored) {
            } finally {
                closeInterface();
            }
        });
        vpnThread.start();
    }

    private void stopVpnSession() {
        running = false;
        if (vpnThread != null) {
            vpnThread.interrupt();
            vpnThread = null;
        }
        closeInterface();
    }

    private void closeInterface() {
        if (vpnInterface != null) {
            try {
                vpnInterface.close();
            } catch (Exception ignored) {
            }
            vpnInterface = null;
        }
    }

    @Override
    public void onDestroy() {
        stopVpnSession();
        super.onDestroy();
    }
}
