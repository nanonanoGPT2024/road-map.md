package com.architect.lowlatency.nio;

import java.io.IOException;
import java.net.InetSocketAddress;
import java.net.StandardSocketOptions;
import java.nio.ByteBuffer;
import java.nio.channels.ClosedChannelException;
import java.nio.channels.SelectionKey;
import java.nio.channels.Selector;
import java.nio.channels.ServerSocketChannel;
import java.nio.channels.SocketChannel;
import java.util.Iterator;
import java.util.Set;

public final class UltraFastNioServer implements Runnable {

    private final int port;
    private final Selector selector;
    private final ServerSocketChannel serverChannel;
    private final ByteBuffer sharedDirectBuffer;
    private volatile boolean running = true;

    public UltraFastNioServer(int port) throws IOException {
        this.port = port;
        // 1. Membuka selector epoll/kqueue internal
        this.selector = Selector.open();

        // 2. Membuka server socket channel
        this.serverChannel = ServerSocketChannel.open();
        this.serverChannel.configureBlocking(false);

        // 3. Konfigurasi Level Soket untuk Latensi Rendah
        this.serverChannel.setOption(StandardSocketOptions.SO_REUSEADDR, true);
        this.serverChannel.setOption(StandardSocketOptions.SO_RCVBUF, 64 * 1024);

        // 4. Bind ke port lokal
        this.serverChannel.bind(new InetSocketAddress(this.port), 1024);

        // 5. Daftarkan event accept ke selector
        this.serverChannel.register(this.selector, SelectionKey.OP_ACCEPT);

        // 6. Alokasi buffer memori native (Off-Heap) 4KB
        this.sharedDirectBuffer = ByteBuffer.allocateDirect(4096);
    }

    @Override
    public void run() {
        System.out.println("[INFO] NIO Server berjalan pada port: " + port);
        try {
            while (running) {
                // Blokir thread sampai ada I/O events yang siap pada OS level
                int readyChannels = selector.select();
                if (readyChannels == 0) {
                    continue;
                }

                Set<SelectionKey> selectedKeys = selector.selectedKeys();
                Iterator<SelectionKey> keyIterator = selectedKeys.iterator();

                while (keyIterator.hasNext()) {
                    SelectionKey key = keyIterator.next();
                    // Sangat krusial: Hapus key dari set segera untuk menghindari pemrosesan ganda
                    keyIterator.remove();

                    if (!key.isValid()) {
                        continue;
                    }

                    try {
                        if (key.isAcceptable()) {
                            handleAccept(key);
                        } else if (key.isReadable()) {
                            handleRead(key);
                        } else if (key.isWritable()) {
                            handleWrite(key);
                        }
                    } catch (IOException e) {
                        System.err.println("[WARN] Client I/O Error: " + e.getMessage());
                        closeChannelQuietly(key);
                    }
                }
            }
        } catch (IOException e) {
            System.err.println("[ERROR] Server Loop Exception: " + e.getMessage());
        } finally {
            cleanup();
        }
    }

    private void handleAccept(SelectionKey key) throws IOException {
        ServerSocketChannel ssc = (ServerSocketChannel) key.channel();
        SocketChannel clientChannel = ssc.accept();
        if (clientChannel != null) {
            clientChannel.configureBlocking(false);

            // TCP_NODELAY menonaktifkan algoritma Nagle (menghilangkan latensi buffering TCP)
            clientChannel.setOption(StandardSocketOptions.TCP_NODELAY, true);
            clientChannel.setOption(StandardSocketOptions.SO_KEEPALIVE, true);

            // Daftarkan channel untuk event Read
            clientChannel.register(selector, SelectionKey.OP_READ);
        }
    }

    private void handleRead(SelectionKey key) throws IOException {
        SocketChannel clientChannel = (SocketChannel) key.channel();
        sharedDirectBuffer.clear(); // Reset pointer: position=0, limit=capacity

        int bytesRead = clientChannel.read(sharedDirectBuffer);

        if (bytesRead == -1) {
            // Client mengirim sinyal FIN (koneksi ditutup secara tertib)
            closeChannelQuietly(key);
            return;
        }

        if (bytesRead > 0) {
            // Balik buffer dari mode tulis ke mode baca
            sharedDirectBuffer.flip();

            // Pemrosesan payload (Contoh: Echo langsung ke client)
            while (sharedDirectBuffer.hasRemaining()) {
                clientChannel.write(sharedDirectBuffer);
            }

            // Jika socket write buffer penuh, alihkan ke OP_WRITE (Dipotong untuk efisiensi contoh)
        }
    }

    private void handleWrite(SelectionKey key) throws IOException {
        // Implementasi flush buffer sisa jika pengiriman parsial terjadi
    }

    private void closeChannelQuietly(SelectionKey key) {
        try {
            key.cancel();
            key.channel().close();
        } catch (IOException ignored) {
        }
    }

    public void stop() {
        this.running = false;
        this.selector.wakeup();
    }

    private void cleanup() {
        try {
            selector.close();
            serverChannel.close();
        } catch (IOException ignored) {
        }
    }

    public static void main(String[] args) throws IOException {
        UltraFastNioServer server = new UltraFastNioServer(8080);
        Thread serverThread = new Thread(server, "NIO-Engine-Thread");
        serverThread.start();
    }
}
