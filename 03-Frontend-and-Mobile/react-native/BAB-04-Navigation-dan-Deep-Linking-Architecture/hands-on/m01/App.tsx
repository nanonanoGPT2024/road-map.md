// navigation/EnterpriseLinkingPipeline.ts
import { LinkingOptions, getStateFromPath } from '@react-navigation/native';
import { Linking } from 'react-native';
import { RootStackParamList } from '../types/navigation';
import { sanitizeAndValidateDeepLink } from './security/DeepLinkValidator';
import { TokenVault } from '../security/TokenVault';
import { NavigationQueue } from './NavigationQueue';

export const EnterpriseLinkingConfig: LinkingOptions<RootStackParamList> = {
  prefixes: ['https://fintech.enterprise.com', 'fintechapp://'],

  // Custom getInitialURL untuk menangani Cold Start dengan validasi
  async getInitialURL() {
    const url = await Linking.getInitialURL();
    if (!url) return null;

    const validation = sanitizeAndValidateDeepLink(url);
    if (!validation.isValid) {
      return null;
    }

    const token = await TokenVault.getAccessToken();
    if (!token) {
      // Simpan rute target ke antrian untuk dieksekusi pasca login
      NavigationQueue.setDeferredPath(url);
      return null;
    }

    return url;
  },

  // Subscribe ke event URL saat aplikasi dalam status Warm/Background
  subscribe(listener) {
    const onReceiveURL = async ({ url }: { url: string }) => {
      const validation = sanitizeAndValidateDeepLink(url);
      if (!validation.isValid) {
        return;
      }

      const token = await TokenVault.getAccessToken();
      if (!token) {
        NavigationQueue.setDeferredPath(url);
        return;
      }

      listener(url);
    };

    const subscription = Linking.addEventListener('url', onReceiveURL);
    return () => subscription.remove();
  },

  // Transformasi konfigurasi URL mapping ke internal navigation stack
  config: {
    screens: {
      App: {
        screens: {
          HomeStack: {
            initialRouteName: 'Feed',
            screens: {
              Feed: 'feed',
              Transfer: 'transfer/target',
            },
          },
        },
      },
      Auth: 'auth',
      NotFound: '*',
    },
  },

  // State reconstruction: Memaksa pembangunan stack history secara manual
  getStateFromPath(path, options) {
    const state = getStateFromPath(path, options);
    if (!state) return undefined;

    // Pastikan jika navigasi ke Transfer, history stack memiliki Feed sebagai index 0
    return {
      ...state,
      routes: state.routes.map((route) => {
        if (route.name === 'App' && route.state) {
          return {
            ...route,
            state: {
              ...route.state,
              routes: route.state.routes.map((subRoute) => {
                if (subRoute.name === 'HomeStack' && subRoute.state) {
                  const hasFeed = subRoute.state.routes.some((r) => r.name === 'Feed');
                  if (!hasFeed) {
                    return {
                      ...subRoute,
                      state: {
                        ...subRoute.state,
                        index: subRoute.state.routes.length,
                        routes: [{ name: 'Feed' }, ...subRoute.state.routes],
                      },
                    };
                  }
                }
                return subRoute;
              }),
            },
          };
        }
        return route;
      }),
    };
  },
};
