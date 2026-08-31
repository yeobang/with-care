import AsyncStorage from "@react-native-async-storage/async-storage";
import { LinkingOptions, NavigationContainer } from "@react-navigation/native";
import { createNativeStackNavigator } from "@react-navigation/native-stack";
import { useEffect, useState } from "react";
import { StatusBar } from "expo-status-bar";
import BoardScreen from "./src/screens/BoardScreen";
import CrewScreen from "./src/screens/CrewScreen";
import HomeScreen from "./src/screens/HomeScreen";
import LedgerScreen from "./src/screens/LedgerScreen";
import SitterScreen from "./src/screens/SitterScreen";
import InviteScreen from "./src/screens/InviteScreen";
import LoginScreen from "./src/screens/LoginScreen";
import { supabase } from "./src/supabase";

const Stack = createNativeStackNavigator();

// 카톡 링크 → 웹 현관: https://<host>/invite/<token> 이 InviteScreen으로 연결된다 (P5)
const linking: LinkingOptions<{}> = {
  prefixes: [],
  config: {
    screens: {
      Invite: "invite/:token",
      Home: "home",
      Login: "",
    },
  },
};

export default function App() {
  const [ready, setReady] = useState(false);
  const [loggedIn, setLoggedIn] = useState(false);

  useEffect(() => {
    (async () => {
      let ok = false;
      if (supabase) {
        const { data } = await supabase.auth.getSession();
        ok = !!data.session;
      }
      if (!ok) ok = !!(await AsyncStorage.getItem("userId")); // dev 헤더 폴백
      setLoggedIn(ok);
      setReady(true);
    })();
  }, []);

  if (!ready) return null;

  return (
    <NavigationContainer linking={linking}>
      <StatusBar style="auto" />
      <Stack.Navigator initialRouteName={loggedIn ? "Home" : "Login"}>
        <Stack.Screen name="Login" component={LoginScreen} options={{ headerShown: false }} />
        <Stack.Screen name="Invite" component={InviteScreen} options={{ headerShown: false }} />
        <Stack.Screen name="Home" component={HomeScreen} options={{ title: "with-care" }} />
        <Stack.Screen
          name="Crew"
          component={CrewScreen}
          options={({ route }: any) => ({ title: route.params?.name ?? "크루" })}
        />
        <Stack.Screen
          name="Ledger"
          component={LedgerScreen}
          options={({ route }: any) => ({ title: `${route.params?.name ?? ""} 장부·정산` })}
        />
        <Stack.Screen
          name="Board"
          component={BoardScreen}
          options={({ route }: any) => ({ title: `${route.params?.name ?? ""} 주간 보드` })}
        />
        <Stack.Screen
          name="Sitter"
          component={SitterScreen}
          options={({ route }: any) => ({ title: `${route.params?.name ?? ""} 시터 공구` })}
        />
      </Stack.Navigator>
    </NavigationContainer>
  );
}
