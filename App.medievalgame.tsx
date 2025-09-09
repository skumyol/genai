import React from 'react';
import createCache from "@emotion/cache";
import { CacheProvider } from "@emotion/react";
import { MedievalGameApp } from './src/components/MedievalGameApp';

const createEmotionCache = () => {
  return createCache({
    key: "mui",
    prepend: true,
  });
};

const emotionCache = createEmotionCache();

const App: React.FC = () => {
  return (
    <CacheProvider value={emotionCache}>
      <MedievalGameApp />
    </CacheProvider>
  );
};

export default App;