// lib/features/portfolio/presentation/widgets/adaptive_portfolio_screen.dart
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

// --- DOMAIN ENUMS & ENTITIES ---
class AssetEntity {
  final String id;
  final String symbol;
  final String name;
  final double price;
  final double changePercentage;

  const AssetEntity({
    required this.id,
    required this.symbol,
    required this.name,
    required this.price,
    required this.changePercentage,
  });
}

// --- REPOSITORY MOCK ---
final List<AssetEntity> kSampleAssets = List.generate(
  50,
  (i) => AssetEntity(
    id: 'asset_$i',
    symbol: 'SYM$i',
    name: 'Enterprise Asset Token $i',
    price: 100.0 + (i * 12.5),
    changePercentage: (i % 2 == 0 ? 1 : -1) * (i * 0.42),
  ),
);

// --- MAIN ADAPTIVE SHELL ---
class AdaptivePortfolioScreen extends StatefulWidget {
  const AdaptivePortfolioScreen({super.key});

  @override
  State<AdaptivePortfolioScreen> createState() => _AdaptivePortfolioScreenState();
}

class _AdaptivePortfolioScreenState extends State<AdaptivePortfolioScreen> {
  AssetEntity? _selectedAsset;

  @override
  void initState() {
    super.initState();
    // Default seleksi untuk skenario layar lebar
    _selectedAsset = kSampleAssets.first;
  }

  void _onAssetSelected(AssetEntity asset, bool isCompact) {
    if (isCompact) {
      // Pada Mobile, dorong route navigasi penuh
      Navigator.of(context).push(
        MaterialPageRoute<void>(
          builder: (context) => AssetDetailMobileScaffold(asset: asset),
        ),
      );
    } else {
      // Pada Desktop/Tablet, ubah in-place state untuk detail pane
      setState(() {
        _selectedAsset = asset;
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    return LayoutBuilder(
      builder: (context, constraints) {
        final double width = constraints.maxWidth;
        final bool isCompact = width < 720.0;
        final bool isTriplePane = width >= 1200.0;

        return Scaffold(
          appBar: AppBar(
            title: const Text('Apex Portfolio Engine'),
            elevation: 0,
            backgroundColor: Theme.of(context).colorScheme.inversePrimary,
          ),
          body: Row(
            children: [
              // PANEL 1: LIST / MASTER VIEW
              SizedBox(
                width: isCompact ? width : (isTriplePane ? 380.0 : 320.0),
                child: AssetMasterList(
                  assets: kSampleAssets,
                  selectedAsset: isCompact ? null : _selectedAsset,
                  onSelect: (asset) => _onAssetSelected(asset, isCompact),
                ),
              ),

              // SEPARATOR JIKA LAYAR LEBAR
              if (!isCompact)
                const VerticalDivider(width: 1, thickness: 1, color: Colors.black12),

              // PANEL 2: DETAIL PRIMARY VIEW (Hanya dirender jika bukan layar compact)
              if (!isCompact)
                Expanded(
                  flex: 3,
                  child: _selectedAsset != null
                      ? AssetDetailPane(asset: _selectedAsset!)
                      : const Center(child: Text('Pilih aset untuk melihat performa')),
                ),

              // PANEL 3: SUPPORTING ACTIONS PANE (Hanya di layar Desktop Large)
              if (isTriplePane) ...[
                const VerticalDivider(width: 1, thickness: 1, color: Colors.black12),
                SizedBox(
                  width: 320.0,
                  child: SupportingExecutionPane(asset: _selectedAsset),
                ),
              ],
            ],
          ),
        );
      },
    );
  }
}

// --- WIDGET: MASTER LIST DENGAN VIRTUALISASI MEMORI ---
class AssetMasterList extends StatelessWidget {
  final List<AssetEntity> assets;
  final AssetEntity? selectedAsset;
  final ValueChanged<AssetEntity> onSelect;

  const AssetMasterList({
    super.key,
    required this.assets,
    required this.selectedAsset,
    required this.onSelect,
  });

  @override
  Widget build(BuildContext context) {
    return ListView.builder(
      itemCount: assets.length,
      itemBuilder: (context, index) {
        final asset = assets[index];
        final bool isSelected = selectedAsset?.id == asset.id;

        return AssetRowItem(
          asset: asset,
          isSelected: isSelected,
          onTap: () => onSelect(asset),
        );
      },
    );
  }
}

// --- WIDGET: ASSET ROW DENGAN HOVER & CONTEXT-MENU NATIVE/DESKTOP CAPABILITIES ---
class AssetRowItem extends StatefulWidget {
  final AssetEntity asset;
  final bool isSelected;
  final VoidCallback onTap;

  const AssetRowItem({
    super.key,
    required this.asset,
    required this.isSelected,
    required this.onTap,
  });

  @override
  State<AssetRowItem> createState() => _AssetRowItemState();
}

class _AssetRowItemState extends State<AssetRowItem> {
  bool _isHovered = false;

  void _showContextMenu(BuildContext context, Offset globalPosition) {
    final RenderBox overlay = Overlay.of(context).context.findRenderObject()! as RenderBox;

    showMenu<String>(
      context: context,
      position: RelativeRect.fromRect(
        globalPosition & const Size(40, 40),
        Offset.zero & overlay.size,
      ),
      items: [
        PopupMenuItem(
          value: 'copy',
          child: const Text('Salin Simbol Asset'),
          onTap: () {
            Clipboard.setData(ClipboardData(text: widget.asset.symbol));
          },
        ),
        const PopupMenuItem(
          value: 'watchlist',
          child: Text('Tambahkan ke Watchlist'),
        ),
      ],
    );
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final isNegative = widget.asset.changePercentage < 0;

    return MouseRegion(
      cursor: SystemMouseCursors.click,
      onEnter: (_) => setState(() => _isHovered = true),
      onExit: (_) => setState(() => _isHovered = false),
      child: GestureDetector(
        onSecondaryTapUp: (details) => _showContextMenu(context, details.globalPosition),
        onTap: widget.onTap,
        child: AnimatedContainer(
          duration: const Duration(milliseconds: 150),
          curve: Curves.easeInOut,
          padding: const EdgeInsets.symmetric(horizontal: 16.0, vertical: 12.0),
          decoration: BoxDecoration(
            color: widget.isSelected
                ? theme.colorScheme.primaryContainer.withAlpha(128)
                : (_isHovered ? theme.colorScheme.surfaceContainerHighest.withAlpha(80) : Colors.transparent),
            border: Border(
              bottom: BorderSide(color: theme.dividerColor.withAlpha(40)),
            ),
          ),
          child: Row(
            children: [
              CircleAvatar(
                radius: 18,
                backgroundColor: theme.colorScheme.secondaryContainer,
                child: Text(
                  widget.asset.symbol.substring(0, 2),
                  style: theme.textTheme.labelMedium?.copyWith(fontWeight: FontWeight.bold),
                ),
              ),
              const SizedBox(width: 12),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      widget.asset.symbol,
                      style: theme.textTheme.titleMedium?.copyWith(fontWeight: FontWeight.w600),
                    ),
                    Text(
                      widget.asset.name,
                      style: theme.textTheme.bodySmall?.copyWith(color: theme.hintColor),
                      overflow: TextOverflow.ellipsis,
                    ),
                  ],
                ),
              ),
              Column(
                crossAxisAlignment: CrossAxisAlignment.end,
                children: [
                  Text(
                    '\$${widget.asset.price.toStringAsFixed(2)}',
                    style: theme.textTheme.bodyMedium?.copyWith(fontWeight: FontWeight.bold),
                  ),
                  Text(
                    '${isNegative ? "" : "+"}${widget.asset.changePercentage.toStringAsFixed(2)}%',
                    style: theme.textTheme.bodySmall?.copyWith(
                      color: isNegative ? Colors.redAccent : Colors.green,
                      fontWeight: FontWeight.w500,
                    ),
                  ),
                ],
              ),
            ],
          ),
        ),
      ),
    );
  }
}

// --- WIDGET: DETAIL PRIMARY VIEW ---
class AssetDetailPane extends StatelessWidget {
  final AssetEntity asset;

  const AssetDetailPane({super.key, required this.asset});

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Padding(
      padding: const EdgeInsets.all(24.0),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(asset.name, style: theme.textTheme.headlineMedium),
                  Text(asset.symbol, style: theme.textTheme.titleMedium?.copyWith(color: theme.hintColor)),
                ],
              ),
              Text(
                '\$${asset.price.toStringAsFixed(2)}',
                style: theme.textTheme.headlineLarge?.copyWith(fontWeight: FontWeight.bold),
              ),
            ],
          ),
          const SizedBox(height: 24),
          // Chart Simulation Box
          Expanded(
            child: Container(
              width: double.infinity,
              decoration: BoxDecoration(
                color: theme.colorScheme.surfaceContainerHighest.withAlpha(50),
                borderRadius: BorderRadius.circular(12),
                border: Border.all(color: theme.dividerColor),
              ),
              child: const Center(
                child: Text('Interactive Canvas Vector Engine Placeholder'),
              ),
            ),
          ),
        ],
      ),
    );
  }
}

// --- WIDGET: THIRD PANE (EXECUTION / ORDERING PANE) ---
class SupportingExecutionPane extends StatelessWidget {
  final AssetEntity? asset;

  const SupportingExecutionPane({super.key, required this.asset});

  @override
  Widget build(BuildContext context) {
    if (asset == null) return const SizedBox.shrink();

    return Padding(
      padding: const EdgeInsets.all(16.0),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text('Eksekusi Order', style: Theme.of(context).textTheme.titleLarge),
          const SizedBox(height: 16),
          TextFormField(
            decoration: const InputDecoration(
              labelText: 'Volume Transaksi',
              border: OutlineInputBorder(),
            ),
            keyboardType: TextInputType.number,
          ),
          const SizedBox(height: 16),
          FilledButton(
            onPressed: () {},
            style: FilledButton.styleFrom(
              minimumSize: const Size(double.infinity, 48),
            ),
            child: Text('Beli ${asset!.symbol}'),
          ),
        ],
      ),
    );
  }
}

// --- SCAFFOLD KHUSUS MOBILE UNTUK NAVIGASI STANDAR PUSH/POP ---
class AssetDetailMobileScaffold extends StatelessWidget {
  final AssetEntity asset;

  const AssetDetailMobileScaffold({super.key, required this.asset});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: Text(asset.symbol),
      ),
      body: AssetDetailPane(asset: asset),
    );
  }
}
