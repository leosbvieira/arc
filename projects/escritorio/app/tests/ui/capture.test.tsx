// Cenários de TELA da captura livre: o que os módulos puros não cobrem porque
// envolvem o React (estado `busy`, o que o usuário digita no meio de um request,
// o que sobrevive a fechar e reabrir o app).
import { act, fireEvent, render, screen, waitFor } from "@testing-library/react-native";

import Capture from "../../src/screens/Capture";
import { flush } from "../../src/captureQueue";
import { secureStoreEmMemoria } from "./setup";

type Resposta = { status: number; body: unknown };

function servidor(handler: (url: string, init?: RequestInit) => Resposta | Promise<Resposta>) {
  jest.mocked(fetch).mockImplementation(async (url, init) => {
    const r = await handler(String(url), init);
    return new Response(JSON.stringify(r.body), {
      status: r.status,
      headers: { "Content-Type": "application/json" },
    });
  });
}

const vazio: Resposta = { status: 200, body: { sessions: [], n: 0, books: [] } };

function postsDeCaptura() {
  return jest
    .mocked(fetch)
    .mock.calls.filter(([url, init]) => String(url).endsWith("/capture") && init?.method === "POST")
    .map(([, init]) => JSON.parse(String(init!.body)));
}

function deferido<T>() {
  let resolve!: (v: T) => void;
  const promise = new Promise<T>((r) => {
    resolve = r;
  });
  return { promise, resolve };
}

beforeEach(() => {
  secureStoreEmMemoria.set("session_token", "jwt-de-teste");
});

async function abrirCaptura() {
  const tela = render(<Capture />);
  // Espera o mount terminar (contador de pendentes, sessões de leitura).
  await waitFor(() => expect(screen.getByLabelText("Enviar captura")).toBeTruthy());
  return tela;
}

test("dois toques em Enviar durante o request mandam UMA captura", async () => {
  const resposta = deferido<Resposta>();
  servidor((url, init) => {
    if (url.endsWith("/capture") && init?.method === "POST") return resposta.promise;
    return vazio;
  });
  await abrirCaptura();

  fireEvent.changeText(screen.getByPlaceholderText(/cobrar a Ana/), "comprar pão");
  fireEvent.press(screen.getByLabelText("Enviar captura"));
  fireEvent.press(screen.getByLabelText("Enviar captura"));
  fireEvent.press(screen.getByLabelText("Enviar captura"));

  await act(async () => {
    resposta.resolve({ status: 200, body: { reply: "✅ anotado" } });
  });
  await waitFor(() => expect(screen.getByText("Anotado. Organiza depois.")).toBeTruthy());
  expect(postsDeCaptura()).toHaveLength(1);
  expect(postsDeCaptura()[0].text).toBe("comprar pão");
});

test("resposta tardia: o que foi digitado durante o request NÃO é apagado", async () => {
  const resposta = deferido<Resposta>();
  servidor((url, init) => {
    if (url.endsWith("/capture") && init?.method === "POST") return resposta.promise;
    return vazio;
  });
  await abrirCaptura();

  const caixa = screen.getByPlaceholderText(/cobrar a Ana/);
  fireEvent.changeText(caixa, "primeira");
  fireEvent.press(screen.getByLabelText("Enviar captura"));
  // O servidor demora; enquanto isso ele já começou a próxima.
  fireEvent.changeText(caixa, "segunda ideia");

  await act(async () => {
    resposta.resolve({ status: 200, body: { reply: "✅ anotado" } });
  });
  await waitFor(() => expect(screen.getByText("Anotado. Organiza depois.")).toBeTruthy());
  expect(caixa.props.value).toBe("segunda ideia");
  expect(postsDeCaptura().map((p) => p.text)).toEqual(["primeira"]);
});

test("sem rede: guardado no aparelho; fechar e reabrir o app mostra a pendência", async () => {
  servidor((url, init) => {
    if (url.endsWith("/capture") && init?.method === "POST") {
      throw new TypeError("Network request failed");
    }
    return vazio;
  });
  const tela = await abrirCaptura();

  fireEvent.changeText(screen.getByPlaceholderText(/cobrar a Ana/), "ligar pro dentista");
  await act(async () => {
    fireEvent.press(screen.getByLabelText("Enviar captura"));
  });
  await waitFor(() => expect(screen.getByText(/guardado no aparelho/)).toBeTruthy());
  expect(screen.getByPlaceholderText(/cobrar a Ana/).props.value).toBe("");

  // "Reinício": desmonta a tela e monta de novo com o MESMO SecureStore.
  tela.unmount();
  render(<Capture />);
  await waitFor(() => expect(screen.getByText(/1 captura\(s\) seguras no aparelho/)).toBeTruthy());
});

test("rede voltou: o flush do App esvazia a fila e o badge some SEM esperar o próximo foco", async () => {
  // Achado do teste no aparelho (PR #1, cenário 1): a tela lia a fila no mesmo "active"
  // em que o App dispara `flush()`, antes do envio, e o badge ficava em "1 captura(s)".
  let semRede = true;
  servidor((url, init) => {
    if (url.endsWith("/capture") && init?.method === "POST") {
      if (semRede) throw new TypeError("Network request failed");
      return { status: 200, body: { reply: "✅ anotado" } };
    }
    return vazio;
  });
  await abrirCaptura();

  fireEvent.changeText(screen.getByPlaceholderText(/cobrar a Ana/), "ligar pro dentista");
  await act(async () => {
    fireEvent.press(screen.getByLabelText("Enviar captura"));
  });
  await waitFor(() => expect(screen.getByText(/1 captura\(s\) seguras no aparelho/)).toBeTruthy());

  // A rede volta e o App (não esta tela) drena a fila, como no "active" real.
  semRede = false;
  await act(async () => {
    await flush();
  });
  await waitFor(() => expect(screen.queryByText(/seguras no aparelho/)).toBeNull());
  // Dois POSTs: a tentativa sem rede e o reenvio do flush — o mesmo texto, uma vez entregue.
  expect(postsDeCaptura().map((p) => p.text)).toEqual(["ligar pro dentista", "ligar pro dentista"]);
});

test("servidor recusou (500): o texto fica na caixa e nada vai pra fila", async () => {
  servidor((url, init) => {
    if (url.endsWith("/capture") && init?.method === "POST") {
      return { status: 500, body: { detail: "erro interno" } };
    }
    return vazio;
  });
  await abrirCaptura();

  fireEvent.changeText(screen.getByPlaceholderText(/cobrar a Ana/), "texto que não pode sumir");
  await act(async () => {
    fireEvent.press(screen.getByLabelText("Enviar captura"));
  });
  await waitFor(() =>
    expect(screen.getByPlaceholderText(/cobrar a Ana/).props.value).toBe("texto que não pode sumir"),
  );
  expect(screen.queryByText(/seguras no aparelho/)).toBeNull();
});

test("resposta tardia: o cadeado marcado na captura NOVA não é desmarcado", async () => {
  const resposta = deferido<Resposta>();
  servidor((url, init) => {
    if (url.endsWith("/capture") && init?.method === "POST") return resposta.promise;
    return vazio;
  });
  await abrirCaptura();

  const caixa = screen.getByPlaceholderText(/cobrar a Ana/);
  fireEvent.changeText(caixa, "primeira");
  fireEvent.press(screen.getByLabelText("Enviar captura"));
  fireEvent.changeText(caixa, "consulta com a psiquiatra");
  fireEvent.press(screen.getByLabelText("Conteúdo sensível"));

  await act(async () => {
    resposta.resolve({ status: 200, body: { reply: "✅ anotado" } });
  });
  await waitFor(() => expect(screen.getByText("Anotado. Organiza depois.")).toBeTruthy());
  expect(caixa.props.value).toBe("consulta com a psiquiatra");
  expect(screen.getByLabelText("Conteúdo sensível").props.accessibilityState?.checked).toBe(true);
});
