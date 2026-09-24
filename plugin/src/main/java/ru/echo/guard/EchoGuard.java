package ru.echo.guard;

import com.google.gson.*;
import net.kyori.adventure.text.Component;
import net.kyori.adventure.text.format.NamedTextColor;
import org.bukkit.Bukkit;
import org.bukkit.OfflinePlayer;
import org.bukkit.command.Command;
import org.bukkit.command.CommandSender;
import org.bukkit.event.*;
import org.bukkit.event.player.AsyncPlayerPreLoginEvent;
import org.bukkit.plugin.java.JavaPlugin;

import javax.crypto.Mac;
import javax.crypto.spec.SecretKeySpec;
import java.net.URI;
import java.net.http.*;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.time.Duration;
import java.time.Instant;
import java.util.*;
import java.util.concurrent.*;
import java.util.logging.Level;

/** No Discord token, no inbound HTTP listener, no Bukkit calls from HTTP handlers. */
public final class EchoGuard extends JavaPlugin implements Listener {
    private final Gson gson = new Gson();
    private final java.util.concurrent.atomic.AtomicBoolean polling = new java.util.concurrent.atomic.AtomicBoolean();
    private final ConcurrentMap<String, Long> attempts = new ConcurrentHashMap<>();
    private final Semaphore loginSlots = new Semaphore(16);
    private final Map<String, JsonObject> acknowledgements = new HashMap<>();
    private HttpClient client;
    private String baseUrl;
    private byte[] secret;
    private int timeout;
    private volatile Set<UUID> whitelistSnapshot = Set.of();
    private volatile boolean configured;
    private volatile long lastSuccess;
    private final java.util.concurrent.atomic.AtomicLong lastWarning = new java.util.concurrent.atomic.AtomicLong();

    @Override public void onEnable() {
        saveDefaultConfig();
        refreshWhitelist();
        Bukkit.getScheduler().runTaskTimer(this, this::refreshWhitelist, 1L, 20L);
        Bukkit.getPluginManager().registerEvents(this, this);
        baseUrl = getConfig().getString("bot-url", "").replaceAll("/+$", "");
        String key = getConfig().getString("bridge-secret", "");
        timeout = Math.max(3, Math.min(15, getConfig().getInt("request-timeout-seconds", 8)));
        try {
            URI uri = URI.create(baseUrl);
            configured = Set.of("http", "https").contains(uri.getScheme()) && uri.getHost() != null
                    && key.matches("[a-fA-F0-9]{64}") && uri.getUserInfo() == null;
        } catch (Exception e) { configured = false; }
        if (!configured) {
            getLogger().severe("Set bot-url and bridge-secret in config.yml, then RESTART. Logins are blocked until configured.");
            return;
        }
        secret = key.getBytes(StandardCharsets.UTF_8);
        client = HttpClient.newBuilder().connectTimeout(Duration.ofSeconds(3))
                .followRedirects(HttpClient.Redirect.NEVER).build();
        Bukkit.getScheduler().runTaskTimerAsynchronously(this, this::poll, 20L, 40L);
        getLogger().info("EchoGuard enabled. Every login requires a single-use Discord confirmation.");
    }

    private void refreshWhitelist() {
        Set<UUID> ids = new HashSet<>();
        for (OfflinePlayer player : Bukkit.getWhitelistedPlayers()) ids.add(player.getUniqueId());
        whitelistSnapshot = Set.copyOf(ids);
    }

    private String sign(byte[] data) throws Exception {
        Mac mac = Mac.getInstance("HmacSHA256");
        mac.init(new SecretKeySpec(secret, "HmacSHA256"));
        return HexFormat.of().formatHex(mac.doFinal(data));
    }

    private JsonObject call(String operation, JsonObject payload) throws Exception {
        String path = "/bridge/" + operation;
        String nonce = UUID.randomUUID().toString().replace("-", "");
        String stamp = Long.toString(Instant.now().getEpochSecond());
        String body = gson.toJson(payload);
        HttpRequest request = HttpRequest.newBuilder(URI.create(baseUrl + path))
                .timeout(Duration.ofSeconds(timeout)).header("Content-Type", "application/json")
                .header("X-Echo-Time", stamp).header("X-Echo-Nonce", nonce)
                .header("X-Echo-Signature", sign((stamp + "\n" + nonce + "\n" + path + "\n" + body).getBytes(StandardCharsets.UTF_8)))
                .POST(HttpRequest.BodyPublishers.ofString(body)).build();
        HttpResponse<String> response = client.send(request, HttpResponse.BodyHandlers.ofString(StandardCharsets.UTF_8));
        if (response.statusCode() != 200) throw new IllegalStateException("Bridge HTTP " + response.statusCode());
        String responseSignature = response.headers().firstValue("X-Echo-Signature").orElse("");
        String expected = sign((nonce + "\n" + response.body()).getBytes(StandardCharsets.UTF_8));
        if (!MessageDigest.isEqual(expected.getBytes(StandardCharsets.US_ASCII), responseSignature.getBytes(StandardCharsets.US_ASCII)))
            throw new IllegalStateException("Invalid bridge response signature");
        JsonObject result = JsonParser.parseString(response.body()).getAsJsonObject();
        if (!result.has("ok") || !result.get("ok").getAsBoolean()) throw new IllegalStateException("Bridge not ready");
        lastSuccess = System.currentTimeMillis();
        return result;
    }

    /** Runs asynchronously; the only whitelist mutation is dispatched to the server thread. */
    private void poll() {
        // Do not queue overlapping polls if the bot or profile service is slow.
        if (!polling.compareAndSet(false, true)) return;
        try { pollOnce(); } finally { polling.set(false); }
    }

    private void pollOnce() {
        if (!isEnabled()) return;
        try {
            attempts.entrySet().removeIf(e -> e.getValue() < System.currentTimeMillis() - 60_000);
            JsonObject response = call("poll", new JsonObject());
            for (JsonElement element : response.getAsJsonArray("commands")) {
                JsonObject command = element.getAsJsonObject();
                String id = command.get("id").getAsString();
                String name = command.get("name").getAsString();
                if (!id.matches("[a-f0-9]{32}") || !name.matches("[A-Za-z0-9_]{3,16}")) continue;
                JsonObject ack = acknowledgements.get(id);
                if (ack == null) {
                    ack = new JsonObject();
                    ack.addProperty("id", id);
                    try {
                        // Name lookup may contact Mojang: keep it away from the tick thread.
                        OfflinePlayer player = Bukkit.getOfflinePlayer(name);
                        Bukkit.getScheduler().callSyncMethod(this, () -> {
                            player.setWhitelisted(true);
                            refreshWhitelist();
                            if (!player.isWhitelisted()) throw new IllegalStateException("Whitelist verification failed");
                            return true;
                        }).get(5, TimeUnit.SECONDS);
                        ack.addProperty("success", true);
                    } catch (Exception e) {
                        ack.addProperty("success", false);
                        ack.addProperty("error", "Whitelist operation failed; see server log");
                        getLogger().log(Level.WARNING, "Unable to whitelist " + name, e);
                    }
                    acknowledgements.put(id, ack);
                }
                call("ack", ack);
                acknowledgements.remove(id);
            }
        } catch (Exception e) { warn(e); }
    }

    @EventHandler(priority = EventPriority.HIGHEST)
    public void onLogin(AsyncPlayerPreLoginEvent event) {
        // Never override a ban, whitelist denial, or another plugin's rejection.
        if (event.getLoginResult() != AsyncPlayerPreLoginEvent.Result.ALLOWED) return;
        if (!configured) { deny(event, "Защита настраивается. Попробуйте позже."); return; }
        String attemptKey = event.getUniqueId().toString();
        long now = System.currentTimeMillis();
        Long previous = attempts.put(attemptKey, now);
        if (previous != null && now - previous < 1500) { deny(event, "Подождите 2 секунды перед повторным входом."); return; }
        if (!loginSlots.tryAcquire()) { deny(event, "Сервис занят. Повторите вход через несколько секунд."); return; }
        try {
            JsonObject payload = new JsonObject();
            payload.addProperty("uuid", event.getUniqueId().toString());
            payload.addProperty("name", event.getName());
            payload.addProperty("ip", event.getAddress().getHostAddress());
            payload.addProperty("whitelisted", whitelistSnapshot.contains(event.getUniqueId()));
            JsonObject result = call("login", payload);
            if (!result.has("allow") || !result.get("allow").getAsBoolean()) {
                deny(event, result.has("message") ? result.get("message").getAsString() : "Подтвердите вход в Discord.");
            }
        } catch (Exception e) {
            deny(event, "Связь с Discord временно недоступна.\nПовторите вход позже.");
            warn(e);
        } finally { loginSlots.release(); }
    }

    private void deny(AsyncPlayerPreLoginEvent event, String message) {
        Component screen = Component.text("ЭХО БЕЗДНЫ", NamedTextColor.LIGHT_PURPLE)
                .append(Component.text("\nЗащита аккаунта\n\n", NamedTextColor.GRAY))
                .append(Component.text(message, NamedTextColor.WHITE));
        event.disallow(AsyncPlayerPreLoginEvent.Result.KICK_OTHER, screen);
    }

    private void warn(Exception e) {
        long now = System.currentTimeMillis();
        long previous = lastWarning.get();
        if (now - previous > 30_000 && lastWarning.compareAndSet(previous, now)) {
            getLogger().warning("Discord bridge unavailable (logins denied): " + e.getClass().getSimpleName());
        }
    }

    @Override public boolean onCommand(CommandSender sender, Command command, String label, String[] args) {
        if (!sender.hasPermission("echoguard.admin")) {
            sender.sendMessage(Component.text("Недостаточно прав.", NamedTextColor.RED));
            return true;
        }
        if (command.getName().equalsIgnoreCase("echoallow")) {
            if (args.length != 1 || !args[0].matches("[A-Za-z0-9_]{3,16}")) {
                sender.sendMessage(Component.text("Использование: /echoallow <ник>", NamedTextColor.YELLOW));
                return true;
            }
            String name = args[0];
            sender.sendMessage(Component.text("Добавляем " + name + " в whitelist…", NamedTextColor.GRAY));
            Bukkit.getScheduler().runTaskAsynchronously(this, () -> {
                try {
                    OfflinePlayer player = Bukkit.getOfflinePlayer(name);
                    Bukkit.getScheduler().runTask(this, () -> {
                        try {
                            player.setWhitelisted(true);
                            refreshWhitelist();
                            if (!player.isWhitelisted()) throw new IllegalStateException("Whitelist verification failed");
                            sender.sendMessage(Component.text("ЭХО БЕЗДНЫ • ", NamedTextColor.LIGHT_PURPLE)
                                    .append(Component.text(name + " допущен к привязке. Код и подтверждение каждого входа в Discord обязательны.", NamedTextColor.GREEN)));
                        } catch (Exception e) {
                            sender.sendMessage(Component.text("Не удалось обновить whitelist. Проверьте консоль.", NamedTextColor.RED));
                            getLogger().log(Level.WARNING, "Whitelist command failed for " + name, e);
                        }
                    });
                } catch (Exception e) {
                    getLogger().log(Level.WARNING, "Profile lookup failed for " + name, e);
                    Bukkit.getScheduler().runTask(this, () -> sender.sendMessage(
                            Component.text("Не удалось найти профиль. Проверьте консоль.", NamedTextColor.RED)));
                }
            });
            return true;
        }
        sender.sendMessage(Component.text("EchoGuard • ", NamedTextColor.LIGHT_PURPLE)
                .append(Component.text(configured && System.currentTimeMillis() - lastSuccess < 15_000
                        ? "Discord bridge online" : "Bridge offline / not configured", NamedTextColor.GRAY)));
        return true;
    }
}
